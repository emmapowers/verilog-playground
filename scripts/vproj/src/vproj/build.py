"""Build bitstream command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .vivado import PROJECT_DIR_DEFAULT, run_vivado_tcl_auto, tcl_quote


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
) -> int:
    """Build bitstream (synthesis + implementation + write_bitstream).

    Args:
        jobs: Number of parallel jobs
        proj_dir: Project directory
        settings: Path to settings64.sh
        quiet: Suppress output
        batch: Force batch mode
        gui: Force GUI mode
        daemon: Force daemon mode
        force: Force full rebuild (reset runs)
        synth_only: Stop after synthesis
        no_bit: Skip bitstream generation
    """
    proj_dir_path = proj_dir or Path(PROJECT_DIR_DEFAULT)
    rptdir = proj_dir_path / "reports"

    # Build the reset logic based on --force flag
    if force:
        reset_logic = """
# Force rebuild - reset all runs
catch { reset_run synth_1 }
catch { reset_run impl_1 }
"""
    else:
        reset_logic = """
# Incremental build - only reset if needed
if {[get_property NEEDS_REFRESH [get_runs synth_1]]} {
    puts "==> Synthesis needs refresh, resetting..."
    reset_run synth_1
    catch { reset_run impl_1 }
} elseif {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
    puts "==> Synthesis incomplete, resetting..."
    reset_run synth_1
    catch { reset_run impl_1 }
}
"""

    # Determine implementation step
    if synth_only:
        impl_step = ""
        bitstream_report = ""
    elif no_bit:
        impl_step = f"""
puts "==> Starting implementation (no bitstream)..."
launch_runs impl_1 -jobs {jobs}
wait_on_run impl_1

if {{[get_property PROGRESS [get_runs impl_1]] != "100%"}} {{
    puts "ERROR: Implementation failed"
    close_project
    exit 4
}}
"""
        bitstream_report = """
open_run impl_1

# Reports directory
file mkdir $rptdir

# Generate reports
report_utilization -file "$rptdir/utilization.rpt"
report_timing_summary -file "$rptdir/timing_summary.rpt" -warn_on_violation

close_project
puts "==> Implementation complete (no bitstream)."
"""
    else:
        impl_step = f"""
puts "==> Starting implementation..."
launch_runs impl_1 -to_step write_bitstream -jobs {jobs}
wait_on_run impl_1

if {{[get_property PROGRESS [get_runs impl_1]] != "100%"}} {{
    puts "ERROR: Implementation failed"
    close_project
    exit 4
}}
"""
        bitstream_report = """
open_run impl_1

# Reports directory
file mkdir $rptdir

# Generate reports
report_utilization -file "$rptdir/utilization.rpt"
report_timing_summary -file "$rptdir/timing_summary.rpt" -warn_on_violation

set bitfile [get_property BITSTREAM.FILE [get_runs impl_1]]
puts "BITSTREAM: $bitfile"

close_project
puts "==> Build complete."
"""

    tcl = f"""
# build.tcl - synth + impl + reports + bit
set proj_dir [file normalize {tcl_quote(proj_dir_path)}]
set rptdir [file normalize {tcl_quote(rptdir)}]

set xprs [glob -nocomplain -types f -directory $proj_dir *.xpr]
if {{[llength $xprs] == 0}} {{
    puts "ERROR: No .xpr found in $proj_dir"
    exit 2
}}
open_project [lindex $xprs 0]

update_compile_order -fileset sources_1

{reset_logic}

puts "==> Starting synthesis..."
launch_runs synth_1 -jobs {jobs}
wait_on_run synth_1

if {{[get_property PROGRESS [get_runs synth_1]] != "100%"}} {{
    puts "ERROR: Synthesis failed"
    close_project
    exit 3
}}

{impl_step}

{bitstream_report}
"""

    mode_desc = []
    if force:
        mode_desc.append("force")
    if synth_only:
        mode_desc.append("synth-only")
    if no_bit:
        mode_desc.append("no-bit")
    mode_str = f" ({', '.join(mode_desc)})" if mode_desc else ""

    if not quiet:
        click.echo(f"==> Building{mode_str} (jobs={jobs})")

    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )

    if code != 0 and not quiet:
        click.echo("Build failed. Check logs in project_files/ for details.", err=True)

    return code
