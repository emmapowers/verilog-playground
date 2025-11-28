"""Build bitstream command with client-side polling and progress display."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markup import escape

from .logs import extract_messages
from .progress import ProgressTable, StageStatus
from .vivado import (
    PROJECT_DIR_DEFAULT,
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
    tcl_quote,
)


def _format_tcl_errors(output: str) -> list[str]:
    """Format error information from TCL output as list of strings."""
    if not output:
        return []
    lines = []
    for line in output.strip().splitlines():
        if line.strip():
            lines.append(f"    [dim]{escape(line)}[/dim]")
    return lines


def poll_run_status(
    run_name: str,
    proj_dir: Optional[Path],
    settings: Optional[Path],
    batch: bool,
    gui: bool,
    daemon: bool,
) -> Optional[StageStatus]:
    """Poll current status of a Vivado run."""
    tcl = f"""
puts "PROGRESS|[get_property PROGRESS [get_runs {run_name}]]"
puts "STATUS|[get_property STATUS [get_runs {run_name}]]"
puts "ELAPSED|[get_property STATS.ELAPSED [get_runs {run_name}]]"
puts "WARNINGS|[get_property WARNING_COUNT [get_runs {run_name}]]"
puts "ERRORS|[get_property ERROR_COUNT [get_runs {run_name}]]"
puts "CRIT_WARNINGS|[get_property CRITICAL_WARNING_COUNT [get_runs {run_name}]]"
"""
    result = run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=True,
        batch=batch,
        gui=gui,
        daemon=daemon,
        return_output=True,
    )

    code, output = result
    if code != 0:
        return None

    # Parse output - only accept first occurrence of each expected key
    expected_keys = {"PROGRESS", "STATUS", "ELAPSED", "WARNINGS", "ERRORS", "CRIT_WARNINGS"}
    data = {}
    for line in output.splitlines():
        if "|" in line:
            key, _, value = line.partition("|")
            key = key.strip()
            # Only accept first occurrence (avoid corrupted duplicate lines)
            if key in expected_keys and key not in data:
                data[key] = value.strip()

    # Parse progress percentage
    progress_str = data.get("PROGRESS", "0%")
    progress = int(progress_str.rstrip("%")) if progress_str.rstrip("%").isdigit() else 0

    return StageStatus(
        name=run_name,
        progress=progress,
        status=data.get("STATUS", "Unknown"),
        elapsed=data.get("ELAPSED", "00:00:00"),
        warnings=int(data.get("WARNINGS", "0") or "0"),
        errors=int(data.get("ERRORS", "0") or "0"),
        critical_warnings=int(data.get("CRIT_WARNINGS", "0") or "0"),
    )


def format_log_summary(proj_dir: Path, run_name: str) -> list[str]:
    """Format summary of warnings/errors from run log as list of strings."""
    log_path = proj_dir / "fpga.runs" / run_name / "runme.log"
    messages = extract_messages(log_path)

    if not messages:
        return []

    result = []
    errors = [(l, m) for l, m in messages if l == "ERROR"]
    critical = [(l, m) for l, m in messages if l == "CRITICAL WARNING"]
    warnings = [(l, m) for l, m in messages if l == "WARNING"]

    run_label = "Synthesis" if run_name == "synth_1" else "Implementation"

    # Summary line
    summary_parts = []
    if errors:
        summary_parts.append(f"[red]{len(errors)} errors[/red]")
    if critical:
        summary_parts.append(f"[yellow]{len(critical)} critical warnings[/yellow]")
    if warnings:
        summary_parts.append(f"[dim]{len(warnings)} warnings[/dim]")

    if summary_parts:
        result.append(f"    {run_label}: {', '.join(summary_parts)}")

    # Show first few of each type
    shown = 0
    max_show = 5

    for level, msg in errors[:max_show]:
        result.append(f"      [red]ERROR:[/red] {escape(msg)}")
        shown += 1

    for level, msg in critical[:max_show - shown]:
        result.append(f"      [yellow]CRITICAL:[/yellow] {escape(msg)}")
        shown += 1

    # Only show regular warnings if no errors/critical
    if shown == 0:
        for level, msg in warnings[:3]:
            result.append(f"      [dim]WARNING:[/dim] {escape(msg)}")

    return result


def build_cmd(
    jobs: int,
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    force: bool = False,
    synth_only: bool = False,
    no_bit: bool = False,
    do_program: bool = False,
) -> int:
    """Build bitstream (synthesis + implementation + write_bitstream).

    Uses client-side polling to monitor progress without blocking the daemon.
    """
    proj_dir_path = proj_dir or Path(PROJECT_DIR_DEFAULT)
    rptdir = proj_dir_path / "reports"
    console = Console()

    # Build mode description
    mode_desc = []
    if force:
        mode_desc.append("force")
    if synth_only:
        mode_desc.append("synth-only")
    if no_bit:
        mode_desc.append("no-bit")
    if do_program:
        mode_desc.append("program")
    mode_str = f" ({', '.join(mode_desc)})" if mode_desc else ""

    if not quiet:
        console.print(f"[bold]==> Building{mode_str} (jobs={jobs})[/bold]")

    xpr = find_xpr(None, proj_dir_path)

    # Determine which stages to show
    stages = ["Synthesis"]
    if not synth_only:
        stages.append("Implementation")
    if do_program and not synth_only and not no_bit:
        stages.append("Programming")

    progress_table = ProgressTable(stages)

    # Build reset logic - force always resets, otherwise try launch first
    if force:
        reset_logic = """
puts "==> Force resetting runs..."
catch { reset_run synth_1 }
catch { reset_run impl_1 }
"""
    else:
        reset_logic = ""

    # --- Step 1: Launch synthesis (non-blocking) ---
    launch_synth_tcl = make_smart_open(xpr) + f"""
update_compile_order -fileset sources_1
{reset_logic}
puts "==> Launching synthesis..."
if {{[catch {{launch_runs synth_1 -jobs {jobs}}} err]}} {{
    if {{[string match "*needs to be reset*" $err]}} {{
        puts "==> Run needs reset, resetting..."
        reset_run synth_1
        catch {{ reset_run impl_1 }}
        launch_runs synth_1 -jobs {jobs}
    }} else {{
        error $err
    }}
}}
puts "LAUNCHED"
"""

    result = run_vivado_tcl_auto(
        launch_synth_tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=True,
        batch=batch,
        gui=gui,
        daemon=daemon,
        return_output=True,
    )
    code, output = result

    if code != 0:
        console.print("[red]==> Failed to launch synthesis[/red]")
        for line in _format_tcl_errors(output):
            console.print(line)
        return code

    # --- Main build loop with single Live context ---
    synth_status = None
    impl_status = None
    bitfile_path = None

    if quiet:
        # Quiet mode - no progress display
        return _build_quiet(
            proj_dir, proj_dir_path, settings, batch, gui, daemon,
            synth_only, no_bit, do_program, jobs, rptdir, console
        )

    # Non-quiet mode - use single Live context for entire build
    progress_table.set_active("Synthesis")

    with Live(progress_table.render(), console=console, refresh_per_second=2) as live:
        # --- Poll synthesis ---
        while True:
            synth_status = poll_run_status("synth_1", proj_dir, settings, batch, gui, daemon)
            if synth_status:
                progress_table.update("Synthesis", synth_status)
            live.update(progress_table.render())

            if synth_status and (synth_status.is_complete() or synth_status.is_failed()):
                break
            time.sleep(1)

        # Check synthesis result
        if synth_status is None or not synth_status.is_complete():
            progress_table.add_message("[red]==> Synthesis failed[/red]")
            for line in format_log_summary(proj_dir_path, "synth_1"):
                progress_table.add_message(line)
            live.update(progress_table.render())
            return 3

        # Add synthesis completion message
        progress_table.add_message(f"[green]==> Synthesis complete[/green] [{synth_status.elapsed}]")
        for line in format_log_summary(proj_dir_path, "synth_1"):
            progress_table.add_message(line)
        live.update(progress_table.render())

        if synth_only:
            run_vivado_tcl_auto(
                make_smart_close(), proj_dir=proj_dir, settings=settings,
                quiet=True, batch=batch, gui=gui, daemon=daemon
            )
            return 0

        # --- Launch implementation ---
        if no_bit:
            impl_step = f"launch_runs impl_1 -jobs {jobs}"
        else:
            impl_step = f"launch_runs impl_1 -to_step write_bitstream -jobs {jobs}"

        launch_impl_tcl = f"""
puts "==> Launching implementation..."
{impl_step}
puts "LAUNCHED"
"""
        result = run_vivado_tcl_auto(
            launch_impl_tcl, proj_dir=proj_dir, settings=settings,
            quiet=True, batch=batch, gui=gui, daemon=daemon, return_output=True
        )
        code, output = result

        if code != 0:
            progress_table.add_message("[red]==> Failed to launch implementation[/red]")
            for line in _format_tcl_errors(output):
                progress_table.add_message(line)
            live.update(progress_table.render())
            return code

        # --- Poll implementation ---
        progress_table.set_active("Implementation")

        while True:
            impl_status = poll_run_status("impl_1", proj_dir, settings, batch, gui, daemon)
            if impl_status:
                progress_table.update("Implementation", impl_status)
            live.update(progress_table.render())

            if impl_status and (impl_status.is_complete() or impl_status.is_failed()):
                break
            time.sleep(1)

        # Check implementation result
        if impl_status is None or not impl_status.is_complete():
            progress_table.add_message("[red]==> Implementation failed[/red]")
            for line in format_log_summary(proj_dir_path, "impl_1"):
                progress_table.add_message(line)
            live.update(progress_table.render())
            return 4

        # Add implementation completion message
        progress_table.add_message(f"[green]==> Implementation complete[/green] [{impl_status.elapsed}]")
        for line in format_log_summary(proj_dir_path, "impl_1"):
            progress_table.add_message(line)
        live.update(progress_table.render())

        # --- Generate reports ---
        reports_tcl = f"""
open_run impl_1
file mkdir {tcl_quote(rptdir)}
report_utilization -file "{tcl_quote(rptdir)}/utilization.rpt"
report_timing_summary -file "{tcl_quote(rptdir)}/timing_summary.rpt" -warn_on_violation
puts "REPORTS_DONE"
""" + make_smart_close()

        run_vivado_tcl_auto(
            reports_tcl, proj_dir=proj_dir, settings=settings,
            quiet=True, batch=batch, gui=gui, daemon=daemon
        )

        # Find bitstream file
        if not no_bit:
            bit_files = list((proj_dir_path / "fpga.runs" / "impl_1").glob("*.bit"))
            if bit_files:
                bitfile_path = bit_files[0]

        # Add build complete message
        if no_bit:
            progress_table.add_message("[bold green]==> Build complete (no bitstream)[/bold green]")
        elif bitfile_path:
            progress_table.add_message("[bold green]==> Build complete[/bold green]")
            progress_table.add_message(f"    Bitstream: {escape(str(bitfile_path))}")
        else:
            progress_table.add_message("[bold green]==> Build complete[/bold green]")
        live.update(progress_table.render())

        # --- Program device if requested ---
        if do_program and not no_bit and bitfile_path:
            progress_table.set_active("Programming")

            from .program import program_device

            def prog_callback(status: StageStatus) -> None:
                progress_table.update("Programming", status)
                live.update(progress_table.render())

            prog_result = program_device(
                bitfile=bitfile_path,
                proj_dir=proj_dir,
                settings=settings,
                quiet=True,
                batch=batch,
                gui=gui,
                daemon=daemon,
                console=console,
                progress_callback=prog_callback,
            )

            if prog_result != 0:
                progress_table.add_message("[red]==> Programming failed[/red]")
                live.update(progress_table.render())
                return prog_result

            progress_table.add_message("[green]==> Device programmed[/green]")
            live.update(progress_table.render())

    return 0


def _build_quiet(
    proj_dir: Optional[Path],
    proj_dir_path: Path,
    settings: Optional[Path],
    batch: bool,
    gui: bool,
    daemon: bool,
    synth_only: bool,
    no_bit: bool,
    do_program: bool,
    jobs: int,
    rptdir: Path,
    console: Console,
) -> int:
    """Build in quiet mode without progress display."""
    # Poll synthesis
    while True:
        synth_status = poll_run_status("synth_1", proj_dir, settings, batch, gui, daemon)
        if synth_status and (synth_status.is_complete() or synth_status.is_failed()):
            break
        time.sleep(1)

    if synth_status is None or not synth_status.is_complete():
        return 3

    if synth_only:
        run_vivado_tcl_auto(
            make_smart_close(), proj_dir=proj_dir, settings=settings,
            quiet=True, batch=batch, gui=gui, daemon=daemon
        )
        return 0

    # Launch implementation
    if no_bit:
        impl_step = f"launch_runs impl_1 -jobs {jobs}"
    else:
        impl_step = f"launch_runs impl_1 -to_step write_bitstream -jobs {jobs}"

    result = run_vivado_tcl_auto(
        f"puts \"==> Launching implementation...\"\n{impl_step}\nputs \"LAUNCHED\"",
        proj_dir=proj_dir, settings=settings,
        quiet=True, batch=batch, gui=gui, daemon=daemon, return_output=True
    )
    if result[0] != 0:
        return result[0]

    # Poll implementation
    while True:
        impl_status = poll_run_status("impl_1", proj_dir, settings, batch, gui, daemon)
        if impl_status and (impl_status.is_complete() or impl_status.is_failed()):
            break
        time.sleep(1)

    if impl_status is None or not impl_status.is_complete():
        return 4

    # Generate reports
    reports_tcl = f"""
open_run impl_1
file mkdir {tcl_quote(rptdir)}
report_utilization -file "{tcl_quote(rptdir)}/utilization.rpt"
report_timing_summary -file "{tcl_quote(rptdir)}/timing_summary.rpt" -warn_on_violation
puts "REPORTS_DONE"
""" + make_smart_close()

    run_vivado_tcl_auto(
        reports_tcl, proj_dir=proj_dir, settings=settings,
        quiet=True, batch=batch, gui=gui, daemon=daemon
    )

    # Program if requested
    if do_program and not no_bit:
        bit_files = list((proj_dir_path / "fpga.runs" / "impl_1").glob("*.bit"))
        if bit_files:
            from .program import program_device
            return program_device(
                bitfile=bit_files[0], proj_dir=proj_dir, settings=settings,
                quiet=True, batch=batch, gui=gui, daemon=daemon, console=console
            )

    return 0
