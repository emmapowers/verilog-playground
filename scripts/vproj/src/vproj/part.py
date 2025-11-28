"""Part (FPGA chip) management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .vivado import (
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
)


def part_info_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Show current FPGA part configuration."""
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set proj [current_project]
set part [get_property part $proj]
set board_part [get_property board_part $proj]

puts "FPGA Part: $part"
if {$board_part ne ""} {
    puts "Note: Part is set via board_part"
}
"""
        + make_smart_close()
    )

    return run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=quiet,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )


def part_set_cmd(
    part: str,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Set the FPGA part directly.

    This also clears any board_part setting.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + f'''
set new_part "{part}"
set proj [current_project]

# Validate the part exists
if {{[llength [get_parts -quiet $new_part]] == 0}} {{
    puts "ERROR: Part '$new_part' not found."
    puts "Use 'vproj part list <pattern>' to find valid parts."
    error "Part not found"
}}

# Clear board_part if set (can't have both)
set board_part [get_property board_part $proj]
if {{$board_part ne ""}} {{
    puts "Clearing board_part (was: $board_part)"
    set_property board_part "" $proj
}}

# Set the new part
set_property part $new_part $proj
puts "FPGA part set to: $new_part"
'''
        + make_smart_close()
    )

    return run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=quiet,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )


def part_list_cmd(
    pattern: Optional[str],
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """List available FPGA parts."""
    filter_pattern = f"*{pattern}*" if pattern else "*"
    # Join parts with newlines to avoid server output buffering issues
    tcl = f'''
set parts [lsort [get_parts {filter_pattern}]]
if {{[llength $parts] == 0}} {{
    puts "NO_PARTS"
}} else {{
    puts "PARTS|[join $parts |]"
}}
puts "DONE"
'''

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
        if not quiet:
            click.echo("Failed to list parts", err=True)
        return code

    # Check for no parts found
    if "NO_PARTS" in output:
        click.echo(f"No parts found matching '{pattern or '*'}'")
        return 0

    # Parse output - format is PARTS|part1|part2|part3...
    parts: list[str] = []
    for line in output.splitlines():
        if line.startswith("PARTS|"):
            parts = line[6:].split("|")
            break

    if not parts:
        click.echo(f"No parts found matching '{pattern or '*'}'")
        return 0

    # Group by family (first part before the '-')
    by_family: dict[str, list[str]] = {}
    for part in parts:
        # e.g., xc7a100tcsg324-1 -> xc7a
        family = part[:4] if len(part) > 4 else part
        if family not in by_family:
            by_family[family] = []
        by_family[family].append(part)

    # Display
    click.echo(f"Parts matching '{pattern or '*'}':\n")
    for family, items in sorted(by_family.items()):
        click.secho(f"  {family}*", fg="cyan", bold=True)
        for part in sorted(items):
            click.echo(f"    {part}")
    click.echo(f"\nTotal: {len(parts)} part(s)")

    return 0
