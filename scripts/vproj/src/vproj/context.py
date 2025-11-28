"""Context object for vproj commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VprojContext:
    """Context object holding common CLI parameters.

    This replaces passing 8+ individual parameters to every command function.
    """

    proj_hint: Optional[Path] = None
    proj_dir: Optional[Path] = None
    settings: Optional[Path] = None
    quiet: bool = False
    no_color: bool = False
    batch: bool = False
    gui: bool = False
    daemon: bool = False

    @classmethod
    def from_click_obj(cls, obj: dict) -> VprojContext:
        """Create context from click's obj dict."""
        return cls(
            proj_hint=obj.get("proj_hint"),
            proj_dir=obj.get("proj_dir"),
            settings=obj.get("settings"),
            quiet=obj.get("quiet", False),
            no_color=obj.get("no_color", False),
            batch=obj.get("batch", False),
            gui=obj.get("gui", False),
            daemon=obj.get("daemon", False),
        )
