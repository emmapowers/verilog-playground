"""Output formatting utilities for vproj CLI."""

from __future__ import annotations

import click


def make_styler(no_color: bool = False):
    """Create styling functions that respect no_color setting.

    Returns a tuple of (label, value, status) functions.

    Usage:
        label, value, status = make_styler(ctx.obj.get("no_color", False))
        click.echo(f"{label('Project:')} {value(info['name'], bold=True)}")
    """

    def label(text: str) -> str:
        """Style a label (e.g., 'Project:', 'Vivado:')."""
        if no_color:
            return text
        return click.style(text, fg="cyan")

    def value(text: str, bold: bool = False) -> str:
        """Style a value, optionally bold."""
        if no_color or not bold:
            return text
        return click.style(text, bold=True)

    def status(text: str, ok: bool) -> str:
        """Style a status indicator (green for ok, red for not ok)."""
        if no_color:
            return text
        return click.style(text, fg="green" if ok else "red")

    return label, value, status


def get_console(no_color: bool = False):
    """Get a Rich Console, optionally with color disabled.

    This is a convenience wrapper to avoid repeated imports and configuration.
    """
    from rich.console import Console

    return Console(no_color=no_color, force_terminal=not no_color)
