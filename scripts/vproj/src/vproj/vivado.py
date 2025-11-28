"""Core Vivado interaction utilities."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import click

PROJECT_DIR_DEFAULT = "project_files"

# File extension to kind mapping
EXT_KIND = {
    # HDL
    ".v": "hdl",
    ".sv": "hdl",
    ".vhd": "hdl",
    ".vhdl": "hdl",
    ".xci": "ip",
    ".bd": "ip",
    # Headers
    ".vh": "header",
    ".svh": "header",
    # Constraints
    ".xdc": "xdc",
    # Other
    ".mem": "other",
    ".tcl": "other",
}

KIND_FILESET = {
    "hdl": "sources_1",
    "header": "sources_1",
    "ip": "sources_1",
    "xdc": "constrs_1",
    "sim": "sim_1",
    "other": "sources_1",
}

VALID_KINDS = tuple(sorted(set(KIND_FILESET.keys())))


def detect_kind(path: Path) -> str:
    """Detect file kind from extension and path."""
    ext = path.suffix.lower()
    k = EXT_KIND.get(ext)
    if k:
        return k
    # Heuristic: HDL under /sim/ or /tb/ folders -> sim fileset
    if ext in {".v", ".sv", ".vhd", ".vhdl"} and any(
        p in {"sim", "tb", "testbench"} for p in path.parts
    ):
        return "sim"
    return "other"


def tcl_quote(p: Path) -> str:
    """Quote a path for TCL."""
    return "{" + str(p) + "}"


def check_vivado_available(
    settings: Optional[Path],
    proj_dir: Optional[Path] = None,
    batch: bool = False,
) -> None:
    """Check that vivado is available, fail with helpful message if not.

    If a daemon/server is running, Vivado doesn't need to be in PATH.
    """
    if settings:
        # Will source settings before running, so vivado will be available
        return

    # Check if daemon/server is running - if so, we don't need vivado in PATH
    if not batch:
        from .daemon import find_server
        pd = Path(proj_dir) if proj_dir else Path(PROJECT_DIR_DEFAULT)
        info = find_server(pd)
        if info.running:
            return

    if shutil.which("vivado") is None:
        raise click.ClickException(
            "Vivado not found in PATH. Either:\n"
            "  1. Source Vivado settings first: source ~/xilinx/2025.1/Vivado/settings64.sh\n"
            "  2. Pass --settings /path/to/settings64.sh"
        )


def run_vivado_tcl(
    tcl: str,
    *,
    settings: Optional[Path],
    vivado: str = "vivado",
    quiet: bool = False,
    return_output: bool = False,
) -> int:
    """Write TCL to a temp file and invoke Vivado batch."""
    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as tf:
        tf.write(tcl)
        tcl_path = Path(tf.name)

    cmd = f'{shlex.quote(vivado)} -mode batch -nolog -nojournal -notrace -source {shlex.quote(str(tcl_path))}'
    try:
        if settings:
            full = f"source {shlex.quote(str(settings))} && {cmd}"
            proc = subprocess.run(
                ["bash", "-lc", full],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        else:
            proc = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        if not quiet:
            click.echo(proc.stdout, nl=True)
        if return_output:
            return (proc.returncode, proc.stdout)
        return proc.returncode
    finally:
        try:
            tcl_path.unlink(missing_ok=True)
        except Exception:
            pass


def run_vivado_tcl_auto(
    tcl: str,
    *,
    proj_dir: Optional[Path] = None,
    settings: Optional[Path],
    quiet: bool = False,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    return_output: bool = False,
) -> int:
    """
    Run TCL code with smart mode selection.

    Decision flow:
    1. --batch: Force batch mode (slow but always works)
    2. --daemon: Force daemon mode (start if needed)
    3. --gui: Force GUI mode (error if no server)
    4. Auto-detect: Check lock file, use GUI if running, else start daemon

    Args:
        tcl: TCL code to execute
        proj_dir: Project directory
        settings: Path to settings64.sh
        quiet: Suppress output
        batch: Force batch mode (skip server)
        gui: Force GUI mode (require existing server)
        daemon: Force daemon mode (start if needed)

    Returns:
        0 on success, non-zero on failure
    """
    pd = Path(proj_dir) if proj_dir else Path(PROJECT_DIR_DEFAULT)

    # Force batch mode
    if batch:
        return run_vivado_tcl(tcl, settings=settings, quiet=quiet, return_output=return_output)

    from .daemon import find_server, send_tcl, start_daemon, get_server_script_path

    info = find_server(pd)

    # Force GUI mode
    if gui:
        if not info.running:
            if info.is_gui:
                raise click.ClickException(
                    "Vivado GUI has the project locked but server not running.\n"
                    "To enable vproj commands in GUI mode, run this in the Vivado TCL console:\n"
                    f"  source {get_server_script_path()}\n\n"
                    "Or install permanently:\n"
                    "  vproj server install"
                )
            else:
                raise click.ClickException(
                    "--gui specified but no Vivado GUI detected (no lock file)."
                )

    # Force daemon mode
    if daemon:
        if info.is_gui:
            raise click.ClickException(
                "Cannot start daemon: Vivado GUI has the project locked.\n"
                "Use --gui mode instead, or close the GUI."
            )
        if not info.running:
            if not quiet:
                click.echo("Starting daemon...", err=True)
            if not start_daemon(proj_dir=pd, settings=settings, quiet=quiet):
                raise click.ClickException("Failed to start daemon")
            info = find_server(pd)

    # Auto-detect mode
    if not info.running:
        if info.is_gui:
            # GUI running but no server
            raise click.ClickException(
                "Vivado GUI has the project locked but server not running.\n"
                "To enable vproj commands in GUI mode, run this in the Vivado TCL console:\n"
                f"  source {get_server_script_path()}\n\n"
                "Or install permanently:\n"
                "  vproj server install\n\n"
                "Or use --batch to force slow batch mode."
            )
        else:
            # No GUI, start daemon
            if not quiet:
                click.echo("Starting daemon...", err=True)
            if not start_daemon(proj_dir=pd, settings=settings, quiet=quiet):
                if not quiet:
                    click.echo("Failed to start daemon, using batch mode", err=True)
                return run_vivado_tcl(tcl, settings=settings, quiet=quiet, return_output=return_output)
            info = find_server(pd)

    # Use server
    try:
        result = send_tcl(tcl, proj_dir=pd)
        if not quiet and result:
            click.echo(result)
        return (0, result) if return_output else 0
    except Exception as e:
        if not quiet:
            click.echo(f"Server error, falling back to batch: {e}", err=True)
        return run_vivado_tcl(tcl, settings=settings, quiet=quiet, return_output=return_output)


def make_smart_open(xpr: Path) -> str:
    """
    Generate TCL to smartly open a project.

    In server mode, checks if project is already open to avoid redundant open_project.
    Returns TCL that sets ::_vproj_did_open to indicate if we opened the project.
    """
    return f"""
# Smart project open - avoid redundant open/close in server mode
proc _vproj_ensure_open {{xpr}} {{
    if {{[llength [get_projects -quiet]] > 0}} {{
        # Project already open - check if it's the right one
        set cur_dir [get_property DIRECTORY [current_project]]
        set want_dir [file dirname $xpr]
        if {{$cur_dir eq $want_dir}} {{
            return 0  ;# Already open, nothing to do
        }}
        # Different project open - close it first
        close_project
    }}
    open_project $xpr
    return 1  ;# We opened it
}}

set _vproj_proj {tcl_quote(xpr.resolve())}
if {{![file exists $_vproj_proj]}} {{
    puts "ERROR: Project not found: $_vproj_proj"
    exit 2
}}
set ::_vproj_did_open [_vproj_ensure_open $_vproj_proj]
set_msg_config -severity INFO -suppress
"""


def make_smart_close() -> str:
    """
    Generate TCL to smartly close a project.

    In server mode (::vproj_server_mode set), keeps project open for next command.
    In batch mode, closes the project.
    """
    return """
# Smart project close - only close if we opened it and not in server mode
reset_msg_config -severity INFO -suppress
if {$::_vproj_did_open && ![info exists ::vproj_server_mode]} {
    close_project
}
"""


# Keep old functions for backwards compatibility during transition
def make_prelude_open_project(xpr: Path) -> str:
    """Generate TCL to open a project with suppressed INFO messages.

    DEPRECATED: Use make_smart_open() instead for server-aware behavior.
    """
    return make_smart_open(xpr)


def make_epilogue_close_project() -> str:
    """Generate TCL to re-enable messages and close project.

    DEPRECATED: Use make_smart_close() instead for server-aware behavior.
    """
    return make_smart_close()


def find_xpr(hint: Optional[Path], proj_dir: Optional[Path] = None) -> Path:
    """
    Find the .xpr project file.

    Prefer .xpr under project_files/ (or user --proj-dir),
    unless an explicit .xpr path is given.
    """
    if hint and hint.is_file() and hint.suffix.lower() == ".xpr":
        return hint.resolve()

    base = Path(".") if hint is None else (hint if hint.is_dir() else hint.parent)
    proj_root = proj_dir or Path(PROJECT_DIR_DEFAULT)
    search_dir = (base / proj_root) if (proj_root != Path(".")) else base

    xprs = sorted(
        search_dir.glob("*.xpr"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not xprs:
        raise click.ClickException(
            f"No .xpr found in {search_dir.resolve()}. "
            f"Run 'vproj import-tcl project.tcl' first."
        )
    if len(xprs) > 1:
        click.echo(f"Found multiple .xpr files; using newest: {xprs[0].name}", err=True)
    return xprs[0].resolve()
