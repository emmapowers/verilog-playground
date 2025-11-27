"""Import project from TCL command."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import click

from .vivado import PROJECT_DIR_DEFAULT, run_vivado_tcl_auto, tcl_quote


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
        click.echo(f"Project imported to {proj_dir_path}")

    return code
