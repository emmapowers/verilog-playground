"""Project file management commands (list/add/remove/mv)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Tuple

import click

from .constants import Fileset
from .context import VprojContext
from .vivado import (
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
    tcl_quote,
)


def list_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    return_data: bool = False,
) -> int | list[tuple[str, str, str]]:
    """List files in sources_1, constrs_1, and sim_1.

    Args:
        return_data: If True, return list of (fileset, path, type) tuples instead of exit code.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set _vproj_result {}
foreach fs [list sources_1 constrs_1 sim_1] {
  set fsobj [get_filesets -quiet $fs]
  if {[llength $fsobj] == 0} { continue }
  foreach f [get_files -of_objects $fsobj] {
    set p [get_property NAME $f]
    set t [get_property FILE_TYPE $f]
    puts "FILE|$fs|$p|$t"
  }
}
"""
        + make_smart_close()
    )

    if return_data:
        result = run_vivado_tcl_auto(
            tcl, proj_dir=proj_dir, settings=settings, quiet=True,
            batch=batch, gui=gui, daemon=daemon, return_output=True
        )
        code, output = result
        if code != 0:
            return []

        files = []
        for line in output.splitlines():
            if line.startswith("FILE|"):
                parts = line[5:].split("|", 2)
                if len(parts) == 3:
                    files.append((parts[0], parts[1], parts[2]))
        return files
    else:
        return run_vivado_tcl_auto(
            tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
            batch=batch, gui=gui, daemon=daemon
        )


def add_files_cmd(
    files: Tuple[Path, ...],
    fileset: Fileset,
    ctx: VprojContext,
) -> int:
    """Add files to a specific fileset.

    This is the unified function for adding files. The individual add_*_cmd
    functions are thin wrappers for backwards compatibility.
    """
    xpr = find_xpr(ctx.proj_hint, ctx.proj_dir)
    lines: list[str] = [make_smart_open(xpr)]

    for p in files:
        lines.append(f'puts "ADD {fileset} {p.name}"')
        lines.append(f"add_files -fileset {fileset} {tcl_quote(p.resolve())}")
        if fileset == Fileset.CONSTRAINTS:
            lines.append(f"set f [get_files -quiet {tcl_quote(p.resolve())}]")
            lines.append(
                "if {[llength $f] > 0} {"
                "set_property USED_IN_SYNTHESIS true $f; "
                "set_property USED_IN_IMPLEMENTATION true $f; }"
            )

    lines.append(make_smart_close())
    tcl = "\n".join(lines)
    code = run_vivado_tcl_auto(
        tcl, proj_dir=ctx.proj_dir, settings=ctx.settings, quiet=ctx.quiet,
        batch=ctx.batch, gui=ctx.gui, daemon=ctx.daemon
    )
    if code == 0 and not ctx.quiet:
        click.echo(f"ADD ({fileset}): done.")
    return code


def _make_ctx(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool,
    gui: bool,
    daemon: bool,
) -> VprojContext:
    """Create VprojContext from individual parameters (for backwards compat)."""
    return VprojContext(
        proj_hint=proj_hint,
        proj_dir=proj_dir,
        settings=settings,
        quiet=quiet,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )


def add_src_cmd(
    files: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add HDL source files (.v, .sv, .vhd, .vh, .svh) to sources_1."""
    ctx = _make_ctx(proj_hint, proj_dir, settings, quiet, batch, gui, daemon)
    return add_files_cmd(files, Fileset.SOURCES, ctx)


def add_xdc_cmd(
    files: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add constraint files (.xdc) to constrs_1."""
    ctx = _make_ctx(proj_hint, proj_dir, settings, quiet, batch, gui, daemon)
    return add_files_cmd(files, Fileset.CONSTRAINTS, ctx)


def add_sim_cmd(
    files: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add testbench files to sim_1."""
    ctx = _make_ctx(proj_hint, proj_dir, settings, quiet, batch, gui, daemon)
    return add_files_cmd(files, Fileset.SIMULATION, ctx)


def add_ip_cmd(
    files: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add IP files (.xci, .bd) to sources_1."""
    ctx = _make_ctx(proj_hint, proj_dir, settings, quiet, batch, gui, daemon)
    return add_files_cmd(files, Fileset.SOURCES, ctx)


def remove_cmd(
    files: Tuple[Path, ...],
    recursive: bool,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Remove files/folders from the project (NEVER deletes from disk)."""
    xpr = find_xpr(proj_hint, proj_dir)
    lines: list[str] = [make_smart_open(xpr)]

    for p in files:
        rp = Path(p).resolve()
        rp_quoted = tcl_quote(rp)

        if recursive:
            # Remove all files under path (folder mode)
            lines.append(f'puts "REMOVE (recursive) {p}"')
            # Match files that start with this path
            pattern = str(rp) + "/*"
            lines.append(f'set objs [get_files -quiet -filter "NAME =~ {{{pattern}}}"]')
            lines.append(
                "if {[llength $objs] > 0} { "
                "puts \"Removing [llength $objs] files\"; "
                "remove_files $objs "
                "} else {"
                f'puts "WARN: No files found under: {p}"; }}'
            )
        else:
            # Remove single file
            lines.append(f'puts "REMOVE {Path(p).name}"')
            lines.append(f"set objs [get_files -quiet {rp_quoted}]")
            lines.append(
                "if {[llength $objs] > 0} { remove_files $objs } else {"
                f'puts "WARN: File not in project: {Path(p)}"; }}'
            )

    lines.append(make_smart_close())
    tcl = "\n".join(lines)
    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
    if code == 0 and not quiet:
        click.echo("REMOVE: done (project only, files still on disk).")
    return code


def _mv_single(
    old_path: Path,
    new_path: Path,
    recursive: bool,
    quiet: bool,
) -> tuple[Path, Path, list[str]]:
    """Move a single file/folder on disk and generate TCL. Returns (old_resolved, new_resolved, tcl_lines)."""
    old_resolved = old_path.resolve()

    # If destination is a directory or path ends with /, move into that directory
    if new_path.is_dir() or str(new_path).endswith("/"):
        new_path = new_path / old_path.name

    new_resolved = new_path.resolve()

    # Handle disk move
    if old_resolved.exists() and not new_resolved.exists():
        # Move on disk
        if old_resolved.is_dir() and not recursive:
            raise click.ClickException(
                f"{old_path} is a directory. Use -r to move directories."
            )
        new_resolved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_resolved), str(new_resolved))
        if not quiet:
            click.echo(f"Moved on disk: {old_path} -> {new_path}")
    elif not old_resolved.exists() and new_resolved.exists():
        if not quiet:
            click.echo(f"WARN: {old_path} doesn't exist on disk, updating project only")
    elif old_resolved.exists() and new_resolved.exists():
        raise click.ClickException(f"Both {old_path} and {new_path} exist on disk")
    else:
        raise click.ClickException(f"Neither {old_path} nor {new_path} exist on disk")

    # Generate TCL for project update
    tcl_lines: list[str] = []

    if recursive or old_resolved.is_dir():
        # Folder move - update all files under old path
        old_str = str(old_resolved)
        new_str = str(new_resolved)
        tcl_lines.append(f'puts "MV (recursive) {old_path} -> {new_path}"')
        pattern = old_str + "/*"
        tcl_lines.append(f"""
set moved 0
foreach f [get_files -quiet -filter "NAME =~ {{{pattern}}}"] {{
    set old_name [get_property NAME $f]
    set fs_name [get_property FILESET_NAME $f]
    set file_type [get_property FILE_TYPE $f]
    # Calculate new path by replacing prefix
    set new_name [string map {{{{{old_str}}} {{{new_str}}}}} $old_name]
    # Remove old file from project
    remove_files $f
    # Add new file to same fileset
    if {{[file exists $new_name]}} {{
        add_files -fileset $fs_name $new_name
        incr moved
    }} else {{
        puts "WARN: New file doesn't exist: $new_name"
    }}
}}
puts "Moved $moved files in project"
""")
    else:
        # Single file move
        tcl_lines.append(f'puts "MV {old_path} -> {new_path}"')
        old_quoted = tcl_quote(old_resolved)
        new_quoted = tcl_quote(new_resolved)
        tcl_lines.append(f"""
set f [get_files -quiet {old_quoted}]
if {{[llength $f] > 0}} {{
    set fs_name [get_property FILESET_NAME $f]
    set file_type [get_property FILE_TYPE $f]
    remove_files $f
    add_files -fileset $fs_name {new_quoted}
    puts "Updated project reference"
}} else {{
    # File not in project, just add new location
    puts "WARN: {old_path} not in project, adding {new_path}"
    # Try to detect fileset from path
    add_files {new_quoted}
}}
""")

    return old_resolved, new_resolved, tcl_lines


def mv_cmd(
    sources: tuple[Path, ...],
    dest: Path,
    recursive: bool,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Move/rename files or folders - handles disk AND project."""
    xpr = find_xpr(proj_hint, proj_dir)

    # With multiple sources, dest must be a directory
    if len(sources) > 1 and not dest.is_dir() and not str(dest).endswith("/"):
        raise click.ClickException(
            f"With multiple sources, destination must be a directory: {dest}"
        )

    # Process each source
    lines: list[str] = [make_smart_open(xpr)]

    for src in sources:
        _, _, tcl_lines = _mv_single(src, dest, recursive, quiet)
        lines.extend(tcl_lines)

    lines.append(make_smart_close())
    tcl = "\n".join(lines)

    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
    if code == 0 and not quiet:
        click.echo("MV: done.")
    return code


# --- Include path management ---


def include_list_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    return_data: bool = False,
) -> int | list[Path]:
    """List include directories from project.

    Args:
        return_data: If True, return list of Path objects instead of exit code.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set inc_dirs [get_property include_dirs [get_filesets sources_1]]
foreach d $inc_dirs {
    puts "INCLUDE|$d"
}
"""
        + make_smart_close()
    )

    if return_data:
        result = run_vivado_tcl_auto(
            tcl, proj_dir=proj_dir, settings=settings, quiet=True,
            batch=batch, gui=gui, daemon=daemon, return_output=True
        )
        code, output = result
        if code != 0:
            return []

        dirs = []
        for line in output.splitlines():
            if line.startswith("INCLUDE|"):
                path_str = line[8:]
                if path_str:
                    dirs.append(Path(path_str))
        return dirs
    else:
        return run_vivado_tcl_auto(
            tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
            batch=batch, gui=gui, daemon=daemon
        )


def include_add_cmd(
    dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add directories to project include_dirs."""
    xpr = find_xpr(proj_hint, proj_dir)
    lines: list[str] = [make_smart_open(xpr)]

    lines.append("set cur [get_property include_dirs [get_filesets sources_1]]")
    for d in dirs:
        resolved = d.resolve()
        lines.append(f'puts "ADD include: {resolved}"')
        lines.append(f"lappend cur {tcl_quote(resolved)}")

    lines.append("set_property include_dirs $cur [get_filesets sources_1]")
    lines.append(make_smart_close())

    tcl = "\n".join(lines)
    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
    if code == 0 and not quiet:
        click.echo("Include directories added.")
    return code


def include_rm_cmd(
    dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Remove directories from project include_dirs."""
    xpr = find_xpr(proj_hint, proj_dir)
    lines: list[str] = [make_smart_open(xpr)]

    lines.append("set cur [get_property include_dirs [get_filesets sources_1]]")
    for d in dirs:
        resolved = d.resolve()
        lines.append(f'puts "REMOVE include: {resolved}"')
        lines.append(f"set idx [lsearch -exact $cur {tcl_quote(resolved)}]")
        lines.append("if {$idx >= 0} { set cur [lreplace $cur $idx $idx] }")

    lines.append("set_property include_dirs $cur [get_filesets sources_1]")
    lines.append(make_smart_close())

    tcl = "\n".join(lines)
    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
    if code == 0 and not quiet:
        click.echo("Include directories removed.")
    return code


def get_include_dirs(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> list[Path]:
    """Get include directories from project for use by check/sim.

    Uses run_vivado_tcl_auto() same as other commands:
    - Daemon if available (fast)
    - Batch mode fallback (slower)

    Returns list of Path objects, empty list on error.
    """
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set inc_dirs [get_property include_dirs [get_filesets sources_1]]
foreach d $inc_dirs {
    puts "INCLUDE|$d"
}
"""
        + make_smart_close()
    )

    result = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=True,
        batch=batch, gui=gui, daemon=daemon, return_output=True
    )

    # Handle return value (code, output) tuple
    code, output = result

    if code != 0:
        return []

    # Parse output
    include_dirs = []
    for line in output.splitlines():
        if line.startswith("INCLUDE|"):
            path_str = line[8:]  # Strip "INCLUDE|"
            if path_str:
                include_dirs.append(Path(path_str))

    return include_dirs


# --- Top module management ---


def get_top_module(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> Optional[str]:
    """Get top module name from project."""
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + """
puts "TOP|[get_property TOP [get_filesets sources_1]]"
"""
        + make_smart_close()
    )

    result = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=True,
        batch=batch, gui=gui, daemon=daemon, return_output=True
    )

    code, output = result
    if code != 0:
        return None

    for line in output.splitlines():
        if line.startswith("TOP|"):
            return line[4:].strip() or None

    return None


def set_top_module(
    module: str,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Set top module for project."""
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + f"""
set_property TOP {module} [get_filesets sources_1]
puts "TOP set to: {module}"
"""
        + make_smart_close()
    )

    if not quiet:
        click.echo(f"==> Setting top module to: {module}")

    return run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )


def get_hierarchy(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    include_nets: bool = False,
) -> list[tuple[str, str, str]]:
    """Get module hierarchy from elaborated design (requires Vivado).

    Args:
        include_nets: If True, include all cells/nets. If False (default),
                      only include module instances.

    Returns list of (instance_name, parent, module_type) tuples.
    """
    xpr = find_xpr(proj_hint, proj_dir)

    if include_nets:
        # Get all cells including nets/primitives
        filter_cmd = "get_cells -hierarchical -quiet"
    else:
        # Only get module instances (non-primitive cells)
        filter_cmd = "get_cells -hierarchical -quiet -filter {IS_PRIMITIVE == false}"

    tcl = (
        make_smart_open(xpr)
        + f"""
# Get top module
set top [get_property TOP [get_filesets sources_1]]
puts "HIER_TOP|$top"

# Elaborate design to get hierarchy
synth_design -rtl -top $top -quiet

# Get cells
foreach cell [{filter_cmd}] {{
    set parent [get_property PARENT $cell]
    set ref [get_property REF_NAME $cell]
    puts "HIER_CELL|$cell|$parent|$ref"
}}

close_design -quiet
"""
        + make_smart_close()
    )

    result = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=True,
        batch=batch, gui=gui, daemon=daemon, return_output=True
    )

    code, output = result
    if code != 0:
        return []

    cells = []
    for line in output.splitlines():
        if line.startswith("HIER_CELL|"):
            parts = line[10:].split("|", 2)
            if len(parts) == 3:
                cells.append((parts[0], parts[1], parts[2]))

    return cells


# --- Project info ---


def info_cmd(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> dict:
    """Get project information and metadata.

    Returns a dict with project info, or empty dict on error.
    """
    xpr = find_xpr(proj_hint, proj_dir)

    tcl = (
        make_smart_open(xpr)
        + r"""
set proj [current_project]

# Basic project info
puts "INFO|project_name|[get_property NAME $proj]"
puts "INFO|project_dir|[get_property DIRECTORY $proj]"

# Part and board
puts "INFO|part|[get_property part $proj]"
puts "INFO|board_part|[get_property board_part $proj]"

# Top module
puts "INFO|top|[get_property TOP [get_filesets sources_1]]"

# Target language
puts "INFO|target_language|[get_property TARGET_LANGUAGE $proj]"

# Simulator
puts "INFO|simulator|[get_property TARGET_SIMULATOR $proj]"

# Vivado version and path
puts "INFO|vivado_version|[version -short]"
puts "INFO|vivado_path|$::env(XILINX_VIVADO)"

# File counts
set src_count [llength [get_files -of_objects [get_filesets sources_1] -quiet]]
set xdc_count [llength [get_files -of_objects [get_filesets constrs_1] -quiet]]
set sim_count [llength [get_files -of_objects [get_filesets sim_1] -quiet]]
puts "INFO|source_count|$src_count"
puts "INFO|constraint_count|$xdc_count"
puts "INFO|sim_count|$sim_count"

# Include dirs
set inc_dirs [get_property include_dirs [get_filesets sources_1]]
puts "INFO|include_dirs|$inc_dirs"
"""
        + make_smart_close()
    )

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
        return {}

    info = {"xpr_path": str(xpr)}
    for line in output.splitlines():
        if line.startswith("INFO|"):
            parts = line[5:].split("|", 1)
            if len(parts) == 2:
                key, value = parts
                info[key] = value

    return info


# Re-export for CLI
__all__ = [
    "list_cmd",
    "add_files_cmd",
    "add_src_cmd",
    "add_xdc_cmd",
    "add_sim_cmd",
    "add_ip_cmd",
    "remove_cmd",
    "mv_cmd",
    "include_list_cmd",
    "include_add_cmd",
    "include_rm_cmd",
    "get_include_dirs",
    "get_top_module",
    "set_top_module",
    "get_hierarchy",
    "info_cmd",
]
