"""Board file management commands."""

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


def board_info_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Show current board configuration."""
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set proj [current_project]
set board_part [get_property board_part $proj]
set part [get_property part $proj]
set board_id [get_property platform.board_id $proj]

puts "FPGA Part: $part"
if {$board_part ne ""} {
    puts "Board Part: $board_part"
}
if {$board_id ne ""} {
    puts "Board ID: $board_id"
}

# Check if board files are installed
if {$board_part ne ""} {
    if {[llength [get_board_parts -quiet $board_part]] > 0} {
        puts "Board Status: Installed"
    } else {
        puts "Board Status: NOT INSTALLED"
        puts "  Run 'vproj board install' to install board files"
    }
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


def board_install_cmd(
    pattern: Optional[str],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Install board files from xhub store.

    If pattern is None, installs board files for the current project's board_part.
    Otherwise, installs boards matching the given pattern.
    """
    if pattern:
        # Install by pattern
        tcl = f'''
puts "Refreshing xhub catalog..."
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]

puts "Searching for boards matching '{pattern}'..."
set items [xhub::get_xitems *{pattern}*]
if {{[llength $items] == 0}} {{
    puts "No boards found matching '{pattern}'"
    exit 1
}}

puts "Found [llength $items] item(s). Installing..."
xhub::install $items
puts "Board files installed successfully."
'''
    else:
        # Install for current project
        xpr = find_xpr(proj_hint, proj_dir)
        tcl = (
            make_smart_open(xpr)
            + r"""
set proj [current_project]
set board_part [get_property board_part $proj]

if {$board_part eq ""} {
    puts "No board_part configured for this project."
    exit 1
}

# Extract board name from board_part (e.g., "digilentinc.com:nexys-a7-100t:part0:1.3" -> "nexys-a7-100t")
set parts [split $board_part ":"]
set board_name [lindex $parts 1]

if {[llength [get_board_parts -quiet $board_part]] > 0} {
    puts "Board '$board_name' is already installed."
    exit 0
}

puts "Refreshing xhub catalog..."
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]

puts "Searching for board '$board_name'..."
set items [xhub::get_xitems *$board_name*]
if {[llength $items] == 0} {
    puts "Board '$board_name' not found in xhub store."
    puts "You may need to install board files manually."
    exit 1
}

puts "Found [llength $items] item(s). Installing..."
xhub::install $items
puts "Board files installed successfully."
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


def board_uninstall_cmd(
    pattern: str,
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Uninstall board files from xhub store."""
    # Filter for installed items only
    tcl = f'''
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]
set all_items [xhub::get_xitems *{pattern}*]
set installed_items {{}}
foreach item $all_items {{
    if {{[get_property IS_INSTALLED $item]}} {{
        lappend installed_items $item
    }}
}}
if {{[llength $installed_items] == 0}} {{
    puts "RESULT|No installed boards found matching '{pattern}'"
}} else {{
    puts "RESULT|Uninstalling [llength $installed_items] item(s)..."
    xhub::uninstall $installed_items
    puts "RESULT|Board files uninstalled."
}}
puts "DONE"
'''

    # Force batch mode - xhub::uninstall doesn't work in daemon mode
    result = run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir,
        settings=settings,
        quiet=True,
        batch=True,
        gui=False,
        daemon=False,
        return_output=True,
    )

    code, output = result
    if code != 0:
        if not quiet:
            click.echo("Failed to uninstall boards", err=True)
        return code

    # Display results
    for line in output.splitlines():
        if line.startswith("RESULT|"):
            click.echo(line[7:])

    return 0


def board_refresh_cmd(
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Refresh the xhub board catalog from GitHub."""
    tcl = '''
puts "RESULT|Refreshing board catalog from GitHub..."
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]
puts "RESULT|Catalog refreshed."
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
            click.echo("Failed to refresh catalog", err=True)
        return code

    for line in output.splitlines():
        if line.startswith("RESULT|"):
            click.echo(line[7:])

    return 0


def board_update_cmd(
    pattern: Optional[str],
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Update installed board files to latest versions."""
    filter_pattern = f"*{pattern}*" if pattern else "*"
    tcl = f'''
puts "RESULT|Refreshing catalog..."
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]
set all_items [xhub::get_xitems {filter_pattern}]
set installed_items {{}}
foreach item $all_items {{
    if {{[get_property IS_INSTALLED $item]}} {{
        lappend installed_items $item
    }}
}}
if {{[llength $installed_items] == 0}} {{
    puts "RESULT|No installed boards found matching '{pattern or '*'}'"
}} else {{
    puts "RESULT|Updating [llength $installed_items] installed board(s)..."
    xhub::update $installed_items
    puts "RESULT|Boards updated."
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
            click.echo("Failed to update boards", err=True)
        return code

    for line in output.splitlines():
        if line.startswith("RESULT|"):
            click.echo(line[7:])

    return 0


def board_set_cmd(
    board_part: str,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Set the board_part on the project.

    Setting board_part automatically sets the FPGA part.
    Fails if the board files are not installed.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + f'''
set board_part "{board_part}"

# Ensure xhub board store path is in board.repoPaths
set xhub_path "$::env(HOME)/.Xilinx/Vivado/2025.1/xhub/board_store/xilinx_board_store/XilinxBoardStore/Vivado/2025.1/boards"
if {{[file exists $xhub_path]}} {{
    set current_paths [get_param board.repoPaths]
    if {{[string first $xhub_path $current_paths] == -1}} {{
        if {{$current_paths eq ""}} {{
            set_param board.repoPaths $xhub_path
        }} else {{
            set_param board.repoPaths "$current_paths:$xhub_path"
        }}
    }}
}}

# Set the board_part (this also sets the part property)
# Vivado will error if the board isn't valid/installed
set_property board_part $board_part [current_project]
puts "Board set to: $board_part"

# Show the FPGA part that was set
set part [get_property part [current_project]]
puts "FPGA part: $part"
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


def board_clear_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Clear the board_part from the project.

    The FPGA part is retained.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r'''
set proj [current_project]
set board_part [get_property board_part $proj]

if {$board_part eq ""} {
    puts "No board_part is set on this project."
} else {
    # Clear the board_part
    set_property board_part "" $proj

    # Show the current state
    set part [get_property part $proj]
    puts "Board cleared."
    puts "FPGA part retained: $part"
}
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


def board_list_cmd(
    pattern: Optional[str],
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """List available boards in xhub store."""
    filter_pattern = f"*{pattern}*" if pattern else "*"
    tcl = f'''
xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]
if {{[catch {{set items [xhub::get_xitems {filter_pattern}]}} err]}} {{
    puts "NO_BOARDS"
}} elseif {{[llength $items] == 0}} {{
    puts "NO_BOARDS"
}} else {{
    foreach item $items {{
        set name [get_property NAME $item]
        set installed [get_property IS_INSTALLED $item]
        puts "BOARD|$name|$installed"
    }}
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
            click.echo("Failed to list boards", err=True)
        return code

    # Check for no boards found
    if "NO_BOARDS" in output:
        click.echo(f"No boards found matching '{pattern or '*'}'")
        return 0

    # Parse output
    boards: list[tuple[str, bool]] = []
    for line in output.splitlines():
        if line.startswith("BOARD|"):
            parts = line[6:].split("|", 1)
            if len(parts) == 2:
                name = parts[0]
                installed = parts[1] == "1"
                boards.append((name, installed))

    if not boards:
        click.echo(f"No boards found matching '{pattern or '*'}'")
        return 0

    # Group by vendor (first part of name)
    by_vendor: dict[str, list[tuple[str, bool]]] = {}
    for name, installed in boards:
        parts = name.split(":")
        vendor = parts[0] if parts else "unknown"
        board_name = parts[2] if len(parts) > 2 else name
        version = parts[3] if len(parts) > 3 else ""
        if vendor not in by_vendor:
            by_vendor[vendor] = []
        by_vendor[vendor].append((board_name, version, installed))

    # Display
    click.echo(f"Boards matching '{pattern or '*'}':\n")
    for vendor, items in sorted(by_vendor.items()):
        click.secho(f"  {vendor}", fg="cyan", bold=True)
        for board_name, version, installed in sorted(items, key=lambda x: (x[0], x[1])):
            status = click.style(" (installed)", fg="green") if installed else ""
            click.echo(f"    {board_name}:{version}{status}")
    click.echo(f"\nTotal: {len(boards)} board(s)")

    return 0
