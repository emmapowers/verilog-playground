"""Program FPGA via JTAG command."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import click
from rich.console import Console
from rich.live import Live

from .progress import ProgressTable, StageStatus
from .vivado import (
    PROJECT_DIR_DEFAULT,
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
    tcl_quote,
)


def find_bitfile(proj_dir: Path) -> Optional[Path]:
    """Find the most recent bitfile in the project runs directory."""
    impl_dir = proj_dir / "fpga.runs" / "impl_1"
    if impl_dir.exists():
        bits = sorted(impl_dir.glob("*.bit"), key=lambda p: p.stat().st_mtime, reverse=True)
        if bits:
            return bits[0]
    return None


def program_cmd(
    bitfile: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Program FPGA over JTAG (standalone command)."""
    console = Console()

    if quiet:
        # Quiet mode - no progress display
        return program_device(
            bitfile=bitfile,
            proj_dir=proj_dir,
            settings=settings,
            quiet=True,
            batch=batch,
            gui=gui,
            daemon=daemon,
            console=console,
        )

    # Non-quiet mode - use progress display
    console.print("[bold]==> Programming FPGA[/bold]")

    progress_table = ProgressTable(["Programming"])
    progress_table.set_active("Programming")

    with Live(progress_table.render(), console=console, refresh_per_second=2) as live:
        def progress_callback(status: StageStatus) -> None:
            progress_table.update("Programming", status)
            live.update(progress_table.render())

        result = program_device(
            bitfile=bitfile,
            proj_dir=proj_dir,
            settings=settings,
            quiet=True,  # We handle output via progress display
            batch=batch,
            gui=gui,
            daemon=daemon,
            console=console,
            progress_callback=progress_callback,
        )

        if result == 0:
            progress_table.add_message("[green]==> Device programmed[/green]")
        else:
            progress_table.add_message("[red]==> Programming failed[/red]")
        live.update(progress_table.render())

    return result


def program_device(
    bitfile: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    console: Optional[Console] = None,
    progress_callback: Optional[Callable[[StageStatus], None]] = None,
) -> int:
    """
    Program FPGA over JTAG.

    This is the core programming function that can be called standalone or
    integrated into a build pipeline with progress display.

    Args:
        bitfile: Path to bitfile, or None to auto-discover
        proj_dir: Project directory
        settings: Path to Vivado settings64.sh
        quiet: Suppress output
        batch: Force batch mode
        gui: Force GUI mode
        daemon: Force daemon mode
        console: Rich console for output
        progress_callback: Optional callback for progress updates

    Returns:
        0 on success, non-zero on failure
    """
    proj_dir_path = proj_dir or Path(PROJECT_DIR_DEFAULT)
    console = console or Console()

    def update_progress(progress: int, status: str, errors: int = 0) -> None:
        if progress_callback:
            progress_callback(StageStatus(
                name="Programming",
                progress=progress,
                status=status,
                errors=errors,
            ))

    # Step 1: Resolve bitfile
    update_progress(0, "Finding bitfile...")

    if bitfile:
        bitfile_path = bitfile.resolve()
    else:
        # Try to find bitfile from project
        bitfile_path = find_bitfile(proj_dir_path)

        # If not found via filesystem, try querying project
        if bitfile_path is None:
            try:
                xpr = find_xpr(None, proj_dir_path)
                tcl = make_smart_open(xpr) + """
set bf ""
set r [get_runs -quiet impl_1]
if {[llength $r]} {
    set bf [get_property DIRECTORY $r]
    set bits [lsort -decreasing [glob -nocomplain -types f [file join $bf *.bit]]]
    if {[llength $bits]} {
        set bf [lindex $bits 0]
    } else {
        set bf ""
    }
}
puts "BITFILE|$bf"
""" + make_smart_close()

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
                if code == 0:
                    for line in output.splitlines():
                        if line.startswith("BITFILE|"):
                            bf = line.split("|", 1)[1].strip()
                            if bf and Path(bf).exists():
                                bitfile_path = Path(bf)
                            break
            except Exception:
                pass

    if bitfile_path is None or not bitfile_path.exists():
        if not quiet:
            console.print("[red]ERROR: Bitstream not found. Pass one via argument or build first.[/red]")
        update_progress(0, "ERROR: No bitfile", errors=1)
        return 3

    if not quiet:
        console.print(f"    Using: {bitfile_path}")

    # Step 2: Connect to hardware
    update_progress(20, "Connecting...")

    tcl = f"""
set bitfile {tcl_quote(bitfile_path)}

# Helper to signal errors - uses error in daemon mode, exit in batch mode
proc vproj_error {{msg code}} {{
    if {{[info exists ::vproj_server_mode] && $::vproj_server_mode}} {{
        error $msg
    }} else {{
        puts $msg
        exit $code
    }}
}}

# Hardware programming - ensure fresh device enumeration
open_hw_manager
catch {{ connect_hw_server -allow_non_jtag }}

# Close any existing target to force refresh (important in daemon mode)
catch {{ close_hw_target }}

# Refresh server to detect newly connected devices
catch {{ refresh_hw_server }}

# Some cables need a moment to enumerate
set tries 10
while {{$tries > 0}} {{
    set ok [catch {{ open_hw_target }} msg]
    if {{!$ok}} {{ break }}
    after 300
    incr tries -1
}}

if {{[catch {{ get_hw_devices }} devs] || [llength $devs] == 0}} {{
    vproj_error "ERROR: No JTAG devices visible. Check cable/permissions." 4
}}

puts "CONNECTED"

current_hw_device [lindex $devs 0]
refresh_hw_device [current_hw_device]

puts "PROGRAMMING"

# Layer 1: Catch explicit TCL errors from programming
if {{[catch {{
    set_property PROGRAM.FILE $bitfile [current_hw_device]
    program_hw_devices [current_hw_device]
}} err]}} {{
    vproj_error "ERROR: Programming failed: $err" 5
}}

# Layer 2: Verify DONE pin is asserted (catches silent failures)
refresh_hw_device [current_hw_device]
set done_status [get_property REGISTER.CONFIG_STATUS.BIT14_DONE_PIN [current_hw_device]]
if {{$done_status != 1}} {{
    vproj_error "ERROR: Programming verification failed - DONE pin not asserted" 5
}}

puts "DONE"
"""

    # Run programming - we need to track progress through output
    result = run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=True,  # We'll handle output ourselves
        batch=batch,
        gui=gui,
        daemon=daemon,
        return_output=True,
    )

    code, output = result

    # Parse output for progress updates
    if "CONNECTED" in output:
        update_progress(40, "Connected")
    if "PROGRAMMING" in output:
        update_progress(60, "Programming device...")
    if "DONE" in output:
        update_progress(100, "Complete")

    if code != 0:
        # Extract the actual error message from output
        error_msg = "Failed"
        for line in output.splitlines():
            if line.startswith("ERROR:"):
                # Extract message after "ERROR: " prefix
                error_msg = line[6:].strip()
                break

        if not quiet:
            console.print(f"[red]ERROR: {error_msg}[/red]")

        # Show 100% red bar to make failure visible
        update_progress(100, error_msg, errors=1)
        return code

    if not quiet:
        console.print("[green]==> Device programmed[/green]")

    return 0
