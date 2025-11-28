"""Shared progress display components for build stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from rich.console import Group, RenderableType
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


@dataclass
class StageStatus:
    """Status of a build stage (synthesis, implementation, programming, etc.)."""

    name: str
    progress: int  # 0-100
    status: str
    elapsed: str = ""
    warnings: int = 0
    errors: int = 0
    critical_warnings: int = 0

    def is_failed(self) -> bool:
        """Check if stage has failed."""
        return self.errors > 0 or "ERROR" in self.status.upper()

    def is_complete(self) -> bool:
        """Check if stage completed successfully."""
        return self.progress == 100 and not self.is_failed()


def make_progress_bar(progress: int, width: int = 30) -> Text:
    """Create a colored progress bar."""
    filled = int(width * progress / 100)
    empty = width - filled
    bar = Text()
    bar.append("\u2588" * filled, style="green")
    bar.append("\u2591" * empty, style="dim")
    bar.append(f" {progress}%", style="bold")
    return bar


def format_stage_info(status: StageStatus) -> str:
    """Format the info string for a stage (status text + counts)."""
    info_parts = []

    if status.status:
        info_parts.append(status.status)
    if status.elapsed and status.elapsed != "00:00:00":
        info_parts.append(f"[{status.elapsed}]")

    # Show warnings/errors
    counts = []
    if status.errors > 0:
        counts.append(f"[red]{status.errors} errors[/red]")
    if status.critical_warnings > 0:
        counts.append(f"[yellow]{status.critical_warnings} critical[/yellow]")
    if status.warnings > 0:
        counts.append(f"[dim]{status.warnings} warnings[/dim]")

    info = " ".join(info_parts)
    if counts:
        info += "  " + ", ".join(counts)

    return info


@dataclass
class ProgressTable:
    """Multi-stage progress display table with messages section."""

    stages: list[str]  # Stage names in order
    statuses: dict[str, Optional[StageStatus]] = field(default_factory=dict)
    active_stage: Optional[str] = None
    messages: list[str] = field(default_factory=list)

    def update(self, stage: str, status: Optional[StageStatus]) -> None:
        """Update status for a stage."""
        self.statuses[stage] = status

    def set_active(self, stage: Optional[str]) -> None:
        """Set the currently active stage."""
        self.active_stage = stage

    def add_message(self, msg: str) -> None:
        """Add a message to the messages section."""
        self.messages.append(msg)

    def _render_table(self) -> Table:
        """Render just the progress table."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Progress", width=40)
        table.add_column("Info")

        for stage in self.stages:
            status = self.statuses.get(stage)
            is_active = stage == self.active_stage

            # Determine label prefix
            if status and status.progress == 100:
                prefix = "\u2713"  # checkmark
            elif is_active:
                prefix = "\u25b6"  # play arrow
            else:
                prefix = " "

            label = f"{prefix} {stage}"

            # Format progress bar and info
            if status is None:
                bar = Text("Waiting...", style="dim")
                info = ""
            else:
                bar = make_progress_bar(status.progress)
                info = format_stage_info(status)

            table.add_row(label, bar, info)

        return table

    def render(self) -> RenderableType:
        """Render the progress table with messages section."""
        table = self._render_table()

        if self.messages:
            # Combine table with separator and messages
            # Use from_markup to render Rich markup tags in messages
            msg_text = Text.from_markup("\n".join(self.messages))
            return Group(table, Rule(style="dim"), msg_text)

        return table
