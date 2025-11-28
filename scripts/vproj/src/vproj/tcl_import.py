"""Import project from TCL command."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import click

from .vivado import PROJECT_DIR_DEFAULT, run_vivado_tcl_auto, tcl_quote
from .utils import display_path


def extract_board_part(tcl_content: str) -> Optional[str]:
    """Extract board_part from TCL content.

    Returns the full board part identifier, e.g. 'digilentinc.com:nexys-a7-100t:part0:1.3'
    """
    match = re.search(
        r'set_property\s+-name\s+"board_part"\s+-value\s+"([^"]+)"',
        tcl_content,
    )
    return match.group(1) if match else None


def get_board_name(board_part: str) -> str:
    """Extract board name from board_part identifier.

    E.g. 'digilentinc.com:nexys-a7-100t:part0:1.3' -> 'nexys-a7-100t'
    """
    parts = board_part.split(":")
    return parts[1] if len(parts) >= 2 else board_part


def make_board_install_tcl(board_part: str, board_name: str) -> str:
    """Generate TCL to check and install board files if missing."""
    return f'''
# Set up xhub board store paths so get_board_parts can find installed boards
catch {{
    set _xhub_base "$::env(HOME)/.Xilinx/Vivado"
    foreach _ver [glob -nocomplain -directory $_xhub_base -type d *] {{
        set _boards_dir [file join $_ver xhub board_store xilinx_board_store XilinxBoardStore Vivado [file tail $_ver] boards]
        if {{[file exists $_boards_dir]}} {{
            set _current_paths [get_param board.repoPaths]
            if {{$_current_paths eq ""}} {{
                set_param board.repoPaths $_boards_dir
            }} elseif {{[string first $_boards_dir $_current_paths] == -1}} {{
                set_param board.repoPaths "$_current_paths:$_boards_dir"
            }}
        }}
    }}
}}

# Auto-install board files if missing
set _board_part "{board_part}"
set _board_name "{board_name}"
if {{[llength [get_board_parts -quiet $_board_part]] == 0}} {{
    puts "Board '$_board_name' not found. Attempting to install from xhub..."
    if {{[catch {{
        xhub::refresh_catalog [xhub::get_xstores xilinx_board_store]
        set _items [xhub::get_xitems *$_board_name*]
        if {{[llength $_items] > 0}} {{
            xhub::install $_items
            puts "Board files installed successfully."
        }} else {{
            puts "WARNING: Could not find board '$_board_name' in xhub store."
            puts "You may need to install board files manually."
        }}
    }} _err]}} {{
        puts "WARNING: Failed to install board files: $_err"
        puts "Continuing without board files - some features may not work."
    }}
}}
'''


def import_tcl_cmd(
    project_tcl: Path,
    workdir: Optional[Path],
    force: bool,
    wipe: bool,
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
    install_board: bool = True,
) -> int:
    """Import/recreate a Vivado project from a TCL script."""
    proj_dir_path = (proj_dir or Path(PROJECT_DIR_DEFAULT)).resolve()
    proj_dir_path.mkdir(parents=True, exist_ok=True)

    if wipe and proj_dir_path.exists():
        shutil.rmtree(proj_dir_path, ignore_errors=True)
        proj_dir_path.mkdir(parents=True, exist_ok=True)

    src = Path(project_tcl).read_text()

    # Re-point the project directory argument in 'create_project'
    # Match: <spaces>create_project <NAME> <DIR> <rest...>
    # Keep NAME & rest, replace only <DIR>.
    create_proj_re = re.compile(
        r'(?m)^(?P<prefix>\s*create_project\s+\S+)\s+(?P<dir>\S+)(?P<rest>.*)$'
    )

    def _replace_proj_dir(m):
        return f'{m.group("prefix")} ' + "{" + str(proj_dir_path) + "}" + m.group("rest")

    src, _ = create_proj_re.subn(_replace_proj_dir, src, count=1)

    # Make original-project root portable
    src = re.sub(
        r'(?m)^set\s+orig_proj_dir\s+.*$',
        'set orig_proj_dir "[file normalize [pwd]/]"',
        src,
    )

    # Some Vivado scripts also have set origin_dir; normalize it too
    src = re.sub(
        r'(?m)^set\s+origin_dir\s+.*$',
        'set origin_dir [file normalize [pwd]]',
        src,
    )

    # Inject -force if requested
    if force:

        def add_force(m):
            line = m.group(0)
            return (
                line
                if "-force" in line
                else line.replace("create_project", "create_project -force", 1)
            )

        src = re.sub(r'(?m)^\s*create_project\b[^\n]*', add_force, src, count=1)

    with tempfile.NamedTemporaryFile("w", suffix=".tcl", delete=False) as tf:
        tf.write(src)
        patched = Path(tf.name)

    pre = ""
    if workdir:
        pre = f"cd {tcl_quote(Path(workdir).resolve())}\n"

    # Auto-install board files if requested and board_part is specified
    if install_board:
        board_part = extract_board_part(src)
        if board_part:
            board_name = get_board_name(board_part)
            pre += make_board_install_tcl(board_part, board_name)

    tcl = pre + f"source {tcl_quote(patched)}\n"

    code = run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )

    try:
        patched.unlink(missing_ok=True)
    except Exception:
        pass

    if code == 0 and not quiet:
        click.echo(f"Project imported to {display_path(proj_dir_path)}")

    return code
