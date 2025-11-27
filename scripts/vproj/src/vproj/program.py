"""Program FPGA via JTAG command."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .vivado import PROJECT_DIR_DEFAULT, run_vivado_tcl_auto, tcl_quote


def program_cmd(
    bitfile: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Program FPGA over JTAG."""
    proj_dir_path = proj_dir or Path(PROJECT_DIR_DEFAULT)

    # If bitfile provided, use it directly
    if bitfile:
        bitfile_tcl = tcl_quote(bitfile.resolve())
        bitfile_resolve_tcl = f'set bitfile [file normalize {bitfile_tcl}]'
    else:
        # Auto-discover from project
        bitfile_resolve_tcl = f"""
# Auto-discover bitfile from project
proc _project_xpr {{}} {{
    set xs [glob -nocomplain -types f {tcl_quote(proj_dir_path)}/*.xpr]
    if {{[llength $xs]}} {{ return [lindex $xs 0] }}
    return ""
}}

proc _bit_from_runs {{}} {{
    if {{![llength [get_projects -quiet]]}} {{ return "" }}
    set r [get_runs -quiet impl_1]
    if {{![llength $r]}} {{ return "" }}
    set bf [get_property BITSTREAM.FILE $r]
    if {{$bf ne "" && [file exists $bf]}} {{ return $bf }}
    set d [get_property DIRECTORY $r]
    set bits [lsort -decreasing [glob -nocomplain -types f [file join $d *.bit]]]
    if {{[llength $bits]}} {{ return [lindex $bits 0] }}
    return ""
}}

proc _bit_from_tree {{}} {{
    set bits [lsort -decreasing [glob -nocomplain -types f -directory {tcl_quote(proj_dir_path)} -recursive *.bit]]
    if {{[llength $bits]}} {{ return [file normalize [lindex $bits 0]] }}
    return ""
}}

set bitfile ""
set xpr [_project_xpr]
if {{$xpr ne ""}} {{
    open_project $xpr
    set bitfile [_bit_from_runs]
    close_project
}}
if {{$bitfile eq ""}} {{
    set bitfile [_bit_from_tree]
}}
"""

    tcl = f"""
{bitfile_resolve_tcl}

if {{$bitfile eq "" || ![file exists $bitfile]}} {{
    puts "ERROR: Bitstream not found. Pass one via argument or build first."
    exit 3
}}
puts "Using bitstream: $bitfile"

# Hardware programming
open_hw
catch {{ connect_hw_server -allow_non_jtag }}

# Some cables need a moment to enumerate
set tries 10
while {{$tries > 0}} {{
    set ok [catch {{ open_hw_target }} msg]
    if {{!$ok}} {{ break }}
    after 300
    incr tries -1
}}

if {{[catch {{ get_hw_devices }} devs] || [llength $devs] == 0}} {{
    puts "ERROR: No JTAG devices visible. Check cable/permissions."
    exit 4
}}

current_hw_device [lindex $devs 0]
refresh_hw_device [current_hw_device]

set_property PROGRAM.FILE $bitfile [current_hw_device]
program_hw_devices [current_hw_device]
refresh_hw_device [current_hw_device]

puts "DONE: Device programmed."
exit 0
"""

    if not quiet:
        click.echo("==> Programming FPGA")

    return run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
