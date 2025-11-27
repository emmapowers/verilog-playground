"""Project file management commands (list/add/remove/mv)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional, Tuple

import click

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
) -> int:
    """List files in sources_1, constrs_1, and sim_1."""
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
    lappend _vproj_result "$fs|$p|$t"
  }
}
set ::_vproj_return [join $_vproj_result "\n"]
"""
        + make_smart_close()
        + r"""
set ::_vproj_return
"""
    )
    return run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )


def _add_files_to_fileset(
    files: Tuple[Path, ...],
    fileset: str,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Add files to a specific fileset."""
    xpr = find_xpr(proj_hint, proj_dir)
    lines: list[str] = [make_smart_open(xpr)]

    for p in files:
        lines.append(f'puts "ADD {fileset} {p.name}"')
        lines.append(f"add_files -fileset {fileset} {tcl_quote(p.resolve())}")
        if fileset == "constrs_1":
            lines.append(f"set f [get_files -quiet {tcl_quote(p.resolve())}]")
            lines.append(
                "if {[llength $f] > 0} {"
                "set_property USED_IN_SYNTHESIS true $f; "
                "set_property USED_IN_IMPLEMENTATION true $f; }"
            )

    lines.append(make_smart_close())
    tcl = "\n".join(lines)
    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )
    if code == 0 and not quiet:
        click.echo(f"ADD ({fileset}): done.")
    return code


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
    return _add_files_to_fileset(
        files, "sources_1", proj_hint, proj_dir, settings, quiet,
        batch=batch, gui=gui, daemon=daemon
    )


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
    return _add_files_to_fileset(
        files, "constrs_1", proj_hint, proj_dir, settings, quiet,
        batch=batch, gui=gui, daemon=daemon
    )


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
    return _add_files_to_fileset(
        files, "sim_1", proj_hint, proj_dir, settings, quiet,
        batch=batch, gui=gui, daemon=daemon
    )


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
    return _add_files_to_fileset(
        files, "sources_1", proj_hint, proj_dir, settings, quiet,
        batch=batch, gui=gui, daemon=daemon
    )


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


def mv_cmd(
    old_path: Path,
    new_path: Path,
    recursive: bool,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Move/rename file or folder - handles disk AND project."""
    xpr = find_xpr(proj_hint, proj_dir)
    old_resolved = old_path.resolve()
    new_resolved = new_path.resolve()

    # Handle disk move
    disk_msg = ""
    if old_resolved.exists() and not new_resolved.exists():
        # Move on disk
        if old_resolved.is_dir() and not recursive:
            raise click.ClickException(
                f"{old_path} is a directory. Use -r to move directories."
            )
        new_resolved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_resolved), str(new_resolved))
        disk_msg = f"Moved on disk: {old_path} -> {new_path}"
    elif not old_resolved.exists() and new_resolved.exists():
        disk_msg = f"WARN: {old_path} doesn't exist on disk, updating project only"
    elif old_resolved.exists() and new_resolved.exists():
        raise click.ClickException(f"Both {old_path} and {new_path} exist on disk")
    else:
        raise click.ClickException(f"Neither {old_path} nor {new_path} exist on disk")

    # Update project
    lines: list[str] = [make_smart_open(xpr)]

    if recursive or old_resolved.is_dir():
        # Folder move - update all files under old path
        old_str = str(old_resolved)
        new_str = str(new_resolved)
        lines.append(f'puts "MV (recursive) {old_path} -> {new_path}"')
        pattern = old_str + "/*"
        lines.append(f"""
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
        lines.append(f'puts "MV {old_path} -> {new_path}"')
        old_quoted = tcl_quote(old_resolved)
        new_quoted = tcl_quote(new_resolved)
        lines.append(f"""
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

    lines.append(make_smart_close())
    tcl = "\n".join(lines)

    if not quiet and disk_msg:
        click.echo(disk_msg)

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
) -> int:
    """List include directories from project."""
    xpr = find_xpr(proj_hint, proj_dir)
    tcl = (
        make_smart_open(xpr)
        + r"""
set inc_dirs [get_property include_dirs [get_filesets sources_1]]
if {[llength $inc_dirs] == 0} {
    puts "No include directories configured"
} else {
    foreach d $inc_dirs {
        puts "INCLUDE|$d"
    }
}
"""
        + make_smart_close()
    )
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
    from io import StringIO
    import sys

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

    # Capture output
    old_stdout = sys.stdout
    sys.stdout = captured = StringIO()

    try:
        code = run_vivado_tcl_auto(
            tcl, proj_dir=proj_dir, settings=settings, quiet=True,
            batch=batch, gui=gui, daemon=daemon
        )
    finally:
        sys.stdout = old_stdout

    if code != 0:
        return []

    # Parse output
    include_dirs = []
    for line in captured.getvalue().splitlines():
        if line.startswith("INCLUDE|"):
            path_str = line[8:]  # Strip "INCLUDE|"
            if path_str:
                include_dirs.append(Path(path_str))

    return include_dirs


# Re-export for CLI
__all__ = [
    "list_cmd",
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
]
