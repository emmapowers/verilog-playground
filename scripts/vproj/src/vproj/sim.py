"""Simulation and syntax checking commands."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

import click
from rich.console import Console
from rich.live import Live
from rich.markup import escape

from .progress import ProgressTable, StageStatus
from .vivado import (
    PROJECT_DIR_DEFAULT,
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
    tcl_quote,
)


@dataclass
class LintMessage:
    """A parsed lint message."""
    level: str  # "error" or "warning"
    file: str
    line: int
    message: str


def _parse_verilator_output(stderr: str) -> tuple[list[LintMessage], list[str]]:
    """Parse verilator output into structured messages.

    Returns (messages, raw_lines) where messages are parsed error/warnings
    and raw_lines is the full output for display.
    """
    messages: list[LintMessage] = []
    raw_lines = stderr.splitlines()

    # Pattern: %Error: /path/file.sv:123:45: Message text
    # Pattern: %Warning-TYPE: /path/file.sv:123:45: Message text
    error_pattern = re.compile(r'^%Error(?:-[A-Z0-9_]+)?:\s*([^:]+):(\d+)(?::\d+)?:\s*(.+)$')
    warning_pattern = re.compile(r'^%Warning-[A-Z0-9_]+:\s*([^:]+):(\d+)(?::\d+)?:\s*(.+)$')

    for line in raw_lines:
        error_match = error_pattern.match(line)
        if error_match:
            messages.append(LintMessage(
                level="error",
                file=Path(error_match.group(1)).name,
                line=int(error_match.group(2)),
                message=error_match.group(3),
            ))
            continue

        warning_match = warning_pattern.match(line)
        if warning_match:
            messages.append(LintMessage(
                level="warning",
                file=Path(warning_match.group(1)).name,
                line=int(warning_match.group(2)),
                message=warning_match.group(3),
            ))

    return messages, raw_lines


def _format_lint_output(stderr: str, use_color: bool) -> tuple[int, int]:
    """Format and print lint output. Returns (error_count, warning_count)."""
    from rich.console import Console
    from rich.markup import escape

    messages, raw_lines = _parse_verilator_output(stderr)

    errors = [m for m in messages if m.level == "error"]
    warnings = [m for m in messages if m.level == "warning"]

    if use_color:
        console = Console(stderr=True)

        # Print colorized output
        for line in raw_lines:
            escaped_line = escape(line)
            if line.startswith("%Error"):
                console.print(f"[bold red]{escaped_line}[/bold red]")
            elif line.startswith("%Warning"):
                console.print(f"[yellow]{escaped_line}[/yellow]")
            elif line.strip().startswith(":") or line.strip().startswith("..."):
                # Note/context lines
                console.print(f"[dim]{escaped_line}[/dim]")
            elif "|" in line and re.match(r'^\s*\d*\s*\|', line):
                # Source code lines (number | code)
                console.print(f"[dim]{escaped_line}[/dim]")
            elif line.strip().startswith("^"):
                # Pointer lines
                console.print(f"[dim]{escaped_line}[/dim]")
            else:
                console.print(escaped_line)

        # Print summary
        console.print()
        if errors or warnings:
            summary_parts = []
            if errors:
                summary_parts.append(f"[bold red]{len(errors)} error{'s' if len(errors) != 1 else ''}[/bold red]")
            if warnings:
                summary_parts.append(f"[yellow]{len(warnings)} warning{'s' if len(warnings) != 1 else ''}[/yellow]")
            console.print(f"[bold]==> Summary: {', '.join(summary_parts)}[/bold]")

            if errors:
                console.print("\n[bold red]Errors:[/bold red]")
                for msg in errors:
                    console.print(f"  [red]{escape(msg.file)}:{msg.line}[/red] {escape(msg.message)}")

            if warnings:
                console.print("\n[bold yellow]Warnings:[/bold yellow]")
                for msg in warnings[:10]:  # Limit to first 10
                    console.print(f"  [yellow]{escape(msg.file)}:{msg.line}[/yellow] {escape(msg.message)}")
                if len(warnings) > 10:
                    console.print(f"  [dim]... and {len(warnings) - 10} more[/dim]")
        else:
            console.print("[bold green]==> No errors or warnings[/bold green]")
    else:
        # Plain output
        click.echo(stderr, err=True)

        # Print plain summary
        click.echo()
        if errors or warnings:
            summary_parts = []
            if errors:
                summary_parts.append(f"{len(errors)} error{'s' if len(errors) != 1 else ''}")
            if warnings:
                summary_parts.append(f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''}")
            click.echo(f"==> Summary: {', '.join(summary_parts)}")

            if errors:
                click.echo("\nErrors:")
                for msg in errors:
                    click.echo(f"  {msg.file}:{msg.line} {msg.message}")

            if warnings:
                click.echo("\nWarnings:")
                for msg in warnings[:10]:
                    click.echo(f"  {msg.file}:{msg.line} {msg.message}")
                if len(warnings) > 10:
                    click.echo(f"  ... and {len(warnings) - 10} more")
        else:
            click.echo("==> No errors or warnings")

    return len(errors), len(warnings)


def _find_tool(name: str) -> Optional[Path]:
    """Find a tool in PATH."""
    path = shutil.which(name)
    return Path(path) if path else None


def _get_project_sources(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    include_sim: bool = True,
) -> List[Path]:
    """Get list of source files from project (requires Vivado)."""
    # This would need to parse Vivado output - for now return empty
    # and let the caller handle it
    return []


def check_cmd(
    files: Optional[tuple],
    use_verilator: bool,
    use_iverilog: bool,
    include_dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    wall: bool = False,
    no_color: bool = False,
) -> int:
    """Fast syntax check without full build.

    Default: verilator --lint-only (very fast)
    Fallback: iverilog -t null

    Args:
        wall: Enable all warnings (-Wall for verilator)
    """
    # Determine which tool to use
    if use_verilator:
        tool = "verilator"
    elif use_iverilog:
        tool = "iverilog"
    else:
        # Auto-detect: prefer verilator for speed
        if _find_tool("verilator"):
            tool = "verilator"
        elif _find_tool("iverilog"):
            tool = "iverilog"
        else:
            raise click.ClickException(
                "No linting tool found. Install verilator or iverilog.\n"
                "  Ubuntu: sudo apt install verilator\n"
                "  Or: sudo apt install iverilog"
            )

    # Get files to check
    if files:
        file_list = [Path(f) for f in files]
    else:
        # Get source files from project
        from .project import list_cmd as project_list_cmd

        project_files = project_list_cmd(
            proj_hint, proj_dir, settings, quiet=True,
            batch=batch, gui=gui, daemon=daemon, return_data=True
        )

        if isinstance(project_files, int) or not project_files:
            raise click.ClickException("Could not get project files. Specify files explicitly.")

        # Filter to only HDL source files (not XDC, not sim_1 testbenches)
        hdl_types = {"SystemVerilog", "Verilog", "Verilog Header", "VHDL"}
        file_list = [
            Path(path) for fileset, path, ftype in project_files
            if ftype in hdl_types and fileset == "sources_1"
        ]

    if not file_list:
        raise click.ClickException("No source files found to check.")

    # Get include directories from project + CLI overrides
    all_includes: List[Path] = []

    # Try to get includes from project
    try:
        from .project import get_include_dirs
        project_includes = get_include_dirs(
            proj_hint, proj_dir, settings,
            batch=batch, gui=gui, daemon=daemon
        )
        all_includes.extend(project_includes)
    except Exception:
        # Project not available or error - continue without project includes
        pass

    # Add CLI-specified includes
    all_includes.extend(include_dirs)

    # Get top module from project for verilator
    top_module: Optional[str] = None
    try:
        from .project import get_top_module
        top_module = get_top_module(
            proj_hint, proj_dir, settings,
            batch=batch, gui=gui, daemon=daemon
        )
    except Exception:
        pass

    file_args = [str(f.resolve()) for f in file_list]

    if not quiet:
        click.echo(f"==> Checking {len(file_list)} files with {tool}")
        if all_includes:
            click.echo(f"    Include paths: {len(all_includes)}")
        if top_module:
            click.echo(f"    Top module: {top_module}")

    # Build command with include paths
    # Note: verilator requires -Ipath format (no space), iverilog accepts both
    if tool == "verilator":
        cmd = ["verilator", "--lint-only", "--timing", "-sv"]
        if wall:
            cmd.append("-Wall")
        else:
            # Syntax check only - don't fail on warnings
            cmd.append("-Wno-fatal")
        # Pass top module to avoid "multiple top modules" error
        if top_module:
            cmd.extend(["--top-module", top_module])
        for inc in all_includes:
            cmd.append(f"-I{inc}")
        cmd.extend(file_args)
    else:  # iverilog
        cmd = ["iverilog", "-t", "null", "-g2012"]
        if wall:
            cmd.append("-Wall")
        # iverilog uses -s for top module
        if top_module:
            cmd.extend(["-s", top_module])
        for inc in all_includes:
            cmd.append(f"-I{inc}")
        cmd.extend(file_args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.stdout and not quiet:
            click.echo(result.stdout)

        # Format and display lint output with colorization and summary
        if result.stderr:
            if tool == "verilator" and not quiet:
                # Use colorized formatter for verilator output
                _format_lint_output(result.stderr, use_color=not no_color)
            else:
                # Plain output for iverilog or quiet mode
                click.echo(result.stderr, err=True)

        if result.returncode == 0:
            if not quiet:
                click.echo("==> Check passed")
        else:
            if not quiet:
                click.echo("==> Check failed", err=True)

        return result.returncode

    except FileNotFoundError:
        raise click.ClickException(f"{tool} not found in PATH")


def sim_cmd(
    testbench: Path,
    use_xsim: bool,
    use_iverilog: bool,
    use_verilator: bool,
    use_fst: bool,
    output: Optional[Path],
    include_dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Run simulation and generate waveform.

    Backends:
    - xsim (default): Vivado's simulator
    - iverilog: Icarus Verilog
    - verilator: Fast Verilog simulator
    """
    pd = proj_dir or Path(PROJECT_DIR_DEFAULT)
    sim_dir = pd / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)

    tb_name = testbench.stem
    ext = ".fst" if use_fst else ".vcd"
    out_file = output or (sim_dir / f"{tb_name}{ext}")

    # Determine backend
    if use_xsim:
        backend = "xsim"
    elif use_iverilog:
        backend = "iverilog"
    elif use_verilator:
        backend = "verilator"
    else:
        # Default to xsim if we have Vivado, else iverilog
        backend = "xsim"

    # Get include directories from project + CLI overrides
    all_includes: List[Path] = []

    # For non-xsim backends, get includes from project
    if backend != "xsim":
        try:
            from .project import get_include_dirs
            project_includes = get_include_dirs(
                proj_hint, proj_dir, settings,
                batch=batch, gui=gui, daemon=daemon
            )
            all_includes.extend(project_includes)
        except Exception:
            pass

    # Add CLI-specified includes
    all_includes.extend(include_dirs)

    console = Console()

    if not quiet:
        console.print(f"[bold]==> Running simulation with {backend}[/bold]")
        console.print(f"    Testbench: {escape(str(testbench))}")
        console.print(f"    Output: {escape(str(out_file))}")
        if all_includes and backend != "xsim":
            console.print(f"    Include paths: {len(all_includes)}")

    if backend == "xsim":
        return _sim_xsim(
            testbench, out_file, proj_hint, proj_dir, settings, quiet,
            batch=batch, gui=gui, daemon=daemon
        )
    elif backend == "iverilog":
        return _sim_iverilog(testbench, out_file, use_fst, all_includes, proj_dir, quiet, console)
    else:
        return _sim_verilator(testbench, out_file, all_includes, proj_dir, quiet, console)


def _sim_xsim(
    testbench: Path,
    output: Path,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool,
    gui: bool,
    daemon: bool,
) -> int:
    """Run simulation with Vivado xsim."""
    xpr = find_xpr(proj_hint, proj_dir)
    tb_name = testbench.stem

    tcl = make_smart_open(xpr) + f"""
# Set testbench as top for simulation
set_property top {tb_name} [get_filesets sim_1]
update_compile_order -fileset sim_1

# Launch simulation
launch_simulation

# Run until completion
run all

# Export waveform
# Note: xsim waveform is in the project sim directory
puts "Simulation complete"
puts "Waveform available in project sim directory"

close_sim
""" + make_smart_close()

    return run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )


def _sim_iverilog(
    testbench: Path,
    output: Path,
    use_fst: bool,
    include_dirs: List[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    console: Optional[Console] = None,
) -> int:
    """Run simulation with Icarus Verilog."""
    if not _find_tool("iverilog"):
        raise click.ClickException("iverilog not found. Install with: sudo apt install iverilog")

    console = console or Console()

    # Gather source files
    sources = []
    for pattern in ["**/*.sv", "**/*.v"]:
        sources.extend(Path(".").glob(pattern))

    if not sources:
        raise click.ClickException("No source files found")

    # Create temp directory for build
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_out = Path(tmpdir) / "sim.out"
        tb_name = testbench.stem

        # Compile with include paths
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o", str(sim_out),
            "-s", tb_name,
        ]
        for inc in include_dirs:
            compile_cmd.append(f"-I{inc}")
        compile_cmd.extend([str(f) for f in sources])

        if quiet:
            # Quiet mode - no progress display
            result = subprocess.run(compile_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return result.returncode

            vvp_cmd = ["vvp", str(sim_out)]
            if use_fst:
                vvp_cmd.append("-fst")

            result = subprocess.run(
                vvp_cmd,
                capture_output=True,
                text=True,
                env={**subprocess.os.environ, "VCD_FILE": str(output.resolve())},
            )
            return result.returncode

        # Non-quiet mode - use progress display
        progress_table = ProgressTable(["Compile", "Simulate"])
        progress_table.set_active("Compile")

        with Live(progress_table.render(), console=console, refresh_per_second=2) as live:
            # Compile stage
            progress_table.update("Compile", StageStatus(
                name="Compile", progress=50, status="Compiling..."
            ))
            live.update(progress_table.render())

            result = subprocess.run(compile_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                progress_table.update("Compile", StageStatus(
                    name="Compile", progress=0, status="Failed", errors=1
                ))
                progress_table.add_message("[red]==> Compilation failed[/red]")
                if result.stderr:
                    for line in result.stderr.strip().splitlines()[:5]:
                        progress_table.add_message(f"    [dim]{escape(line)}[/dim]")
                live.update(progress_table.render())
                return result.returncode

            progress_table.update("Compile", StageStatus(
                name="Compile", progress=100, status="Complete"
            ))
            progress_table.add_message("[green]==> Compilation complete[/green]")
            live.update(progress_table.render())

            # Simulate stage
            progress_table.set_active("Simulate")
            progress_table.update("Simulate", StageStatus(
                name="Simulate", progress=50, status="Running..."
            ))
            live.update(progress_table.render())

            vvp_cmd = ["vvp", str(sim_out)]
            if use_fst:
                vvp_cmd.append("-fst")

            result = subprocess.run(
                vvp_cmd,
                capture_output=True,
                text=True,
                env={**subprocess.os.environ, "VCD_FILE": str(output.resolve())},
            )

            if result.returncode != 0:
                progress_table.update("Simulate", StageStatus(
                    name="Simulate", progress=0, status="Failed", errors=1
                ))
                progress_table.add_message("[red]==> Simulation failed[/red]")
                if result.stderr:
                    for line in result.stderr.strip().splitlines()[:5]:
                        progress_table.add_message(f"    [dim]{escape(line)}[/dim]")
                live.update(progress_table.render())
                return result.returncode

            progress_table.update("Simulate", StageStatus(
                name="Simulate", progress=100, status="Complete"
            ))
            progress_table.add_message("[green]==> Simulation complete[/green]")
            progress_table.add_message(f"    Waveform: {escape(str(output))}")
            live.update(progress_table.render())

        return 0


def _sim_verilator(
    testbench: Path,
    output: Path,
    include_dirs: List[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    console: Optional[Console] = None,
) -> int:
    """Run simulation with Verilator."""
    if not _find_tool("verilator"):
        raise click.ClickException("verilator not found. Install with: sudo apt install verilator")

    console = console or Console()

    # Gather source files
    sources = []
    for pattern in ["**/*.sv", "**/*.v"]:
        sources.extend(Path(".").glob(pattern))

    if not sources:
        raise click.ClickException("No source files found")

    tb_name = testbench.stem

    with tempfile.TemporaryDirectory() as tmpdir:
        # Compile with verilator and include paths
        compile_cmd = [
            "verilator",
            "--binary",
            "--trace",
            "-j", "0",
            "-Wall",
            "-Wno-fatal",
            "--timing",
            "--top", tb_name,
            "-Mdir", tmpdir,
        ]
        for inc in include_dirs:
            compile_cmd.append(f"-I{inc}")
        compile_cmd.extend([str(f) for f in sources])

        if quiet:
            # Quiet mode - no progress display
            result = subprocess.run(compile_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return result.returncode

            exe = Path(tmpdir) / f"V{tb_name}"
            if not exe.exists():
                return 1

            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=tmpdir)

            trace = Path(tmpdir) / "trace.vcd"
            if trace.exists():
                shutil.move(str(trace), str(output))

            return result.returncode

        # Non-quiet mode - use progress display
        progress_table = ProgressTable(["Compile", "Simulate"])
        progress_table.set_active("Compile")

        with Live(progress_table.render(), console=console, refresh_per_second=2) as live:
            # Compile stage
            progress_table.update("Compile", StageStatus(
                name="Compile", progress=50, status="Compiling..."
            ))
            live.update(progress_table.render())

            result = subprocess.run(compile_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                progress_table.update("Compile", StageStatus(
                    name="Compile", progress=0, status="Failed", errors=1
                ))
                progress_table.add_message("[red]==> Compilation failed[/red]")
                if result.stderr:
                    for line in result.stderr.strip().splitlines()[:5]:
                        progress_table.add_message(f"    [dim]{escape(line)}[/dim]")
                live.update(progress_table.render())
                return result.returncode

            progress_table.update("Compile", StageStatus(
                name="Compile", progress=100, status="Complete"
            ))
            progress_table.add_message("[green]==> Compilation complete[/green]")
            live.update(progress_table.render())

            # Simulate stage
            exe = Path(tmpdir) / f"V{tb_name}"
            if not exe.exists():
                progress_table.add_message(f"[red]==> Verilator executable not found: {escape(str(exe))}[/red]")
                live.update(progress_table.render())
                return 1

            progress_table.set_active("Simulate")
            progress_table.update("Simulate", StageStatus(
                name="Simulate", progress=50, status="Running..."
            ))
            live.update(progress_table.render())

            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=tmpdir)

            if result.returncode != 0:
                progress_table.update("Simulate", StageStatus(
                    name="Simulate", progress=0, status="Failed", errors=1
                ))
                progress_table.add_message("[red]==> Simulation failed[/red]")
                if result.stderr:
                    for line in result.stderr.strip().splitlines()[:5]:
                        progress_table.add_message(f"    [dim]{escape(line)}[/dim]")
                live.update(progress_table.render())
                return result.returncode

            # Move trace file
            trace = Path(tmpdir) / "trace.vcd"
            if trace.exists():
                shutil.move(str(trace), str(output))

            progress_table.update("Simulate", StageStatus(
                name="Simulate", progress=100, status="Complete"
            ))
            progress_table.add_message("[green]==> Simulation complete[/green]")
            progress_table.add_message(f"    Waveform: {escape(str(output))}")
            live.update(progress_table.render())

        return 0


__all__ = ["sim_cmd", "check_cmd"]
