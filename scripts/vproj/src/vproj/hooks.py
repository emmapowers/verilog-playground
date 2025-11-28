"""Git hook management for vproj."""

from __future__ import annotations

import stat
import subprocess
from enum import StrEnum, auto
from pathlib import Path


class HookMode(StrEnum):
    """Mode for handling project.tcl changes in pre-commit hook."""

    WARN = auto()  # Warn if changed, allow commit
    BLOCK = auto()  # Block if changed
    UPDATE = auto()  # Auto-stage if changed


def find_git_root() -> Path | None:
    """Find the root of the current git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None


def get_hook_path(git_root: Path) -> Path:
    """Get the path to the pre-commit hook."""
    return git_root / ".git" / "hooks" / "pre-commit"


def get_hook_script(mode: HookMode) -> str:
    """Generate hook script with configured mode."""
    if mode == HookMode.BLOCK:
        change_handler = """echo "Error: project.tcl has uncommitted changes after export" >&2
    echo "Run 'git add project.tcl' or use 'vproj hook install update'" >&2
    exit 1"""
    elif mode == HookMode.WARN:
        change_handler = 'echo "Warning: project.tcl changed but not staged" >&2'
    else:  # UPDATE
        change_handler = """git add project.tcl
    echo "Auto-staged updated project.tcl" """

    return f"""#!/bin/sh
# VPROJ_HOOK - managed by vproj, do not edit manually
# mode={mode.value}

# Export project.tcl before commit
if ! vproj -q export-tcl 2>/dev/null; then
    echo "Warning: vproj export-tcl failed (Vivado unavailable?)" >&2
fi

# Check if project.tcl changed
if git diff --name-only project.tcl 2>/dev/null | grep -q project.tcl; then
    {change_handler}
fi
"""


def get_current_mode(git_root: Path) -> HookMode | None:
    """Get the current mode from installed hook, or None if not installed."""
    hook_path = get_hook_path(git_root)
    if not hook_path.exists():
        return None
    content = hook_path.read_text()
    if "VPROJ_HOOK" not in content:
        return None
    # Parse mode= line
    for line in content.splitlines():
        if line.startswith("# mode="):
            return HookMode(line.split("=")[1])
    return HookMode.WARN  # Default for old hooks


def install_hook(git_root: Path, mode: HookMode) -> tuple[bool, str]:
    """Install the pre-commit hook. Returns (success, message)."""
    hook_path = get_hook_path(git_root)

    # Check if another hook exists
    if hook_path.exists():
        content = hook_path.read_text()
        if "VPROJ_HOOK" not in content:
            return False, f"Pre-commit hook already exists at {hook_path}"

    # Write hook
    hook_path.write_text(get_hook_script(mode))
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True, f"Installed pre-commit hook (mode={mode.value})"


def uninstall_hook(git_root: Path) -> tuple[bool, str]:
    """Uninstall the pre-commit hook. Returns (success, message)."""
    hook_path = get_hook_path(git_root)

    if not hook_path.exists():
        return False, "No pre-commit hook installed"

    content = hook_path.read_text()
    if "VPROJ_HOOK" not in content:
        return False, "Pre-commit hook exists but was not installed by vproj"

    hook_path.unlink()
    return True, "Removed pre-commit hook"
