"""Shared utility functions for vproj."""

from pathlib import Path


def display_path(path: str | Path) -> str:
    """Format a path for display, using relative path if under cwd.

    Converts absolute paths to relative paths when they are children
    of the current working directory. Returns absolute paths unchanged
    if they are outside cwd.

    Args:
        path: The path to format (string or Path object)

    Returns:
        Formatted path string for display
    """
    if not path:
        return ""
    try:
        return str(Path(path).relative_to(Path.cwd()))
    except ValueError:
        # Path is not relative to cwd, return as-is
        return str(path)
