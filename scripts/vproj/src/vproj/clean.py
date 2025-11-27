"""Clean build artifacts command."""

from __future__ import annotations

import shutil
from pathlib import Path

import click


def clean_cmd(quiet: bool) -> int:
    """Remove Vivado build artifacts."""
    cwd = Path(".")
    removed = []

    # Remove vivado*.log files
    for f in cwd.glob("vivado*.log"):
        f.unlink()
        removed.append(str(f))

    # Remove vivado*.jou files
    for f in cwd.glob("vivado*.jou"):
        f.unlink()
        removed.append(str(f))

    # Remove .Xil directory
    xil_dir = cwd / ".Xil"
    if xil_dir.exists():
        shutil.rmtree(xil_dir)
        removed.append(".Xil/")

    if not quiet:
        if removed:
            click.echo(f"Removed: {', '.join(removed)}")
        else:
            click.echo("Nothing to clean.")

    return 0
