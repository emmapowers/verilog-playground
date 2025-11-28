"""Log viewing and filtering utilities."""

from __future__ import annotations

import os
import re
from enum import StrEnum, auto
from pathlib import Path
from typing import Optional

from .vivado import PROJECT_DIR_DEFAULT


class LogType(StrEnum):
    """Types of logs that can be viewed."""

    SYNTH = auto()
    IMPL = auto()
    DAEMON = auto()
    SIM = auto()


class Severity(StrEnum):
    """Message severity levels."""

    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL WARNING"


def get_log_path(
    log_type: LogType,
    proj_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Get the path to a log file.

    Args:
        log_type: Type of log to get
        proj_dir: Project directory (default: project_files)

    Returns:
        Path to the log file, or None if not found
    """
    pd = proj_dir or Path(PROJECT_DIR_DEFAULT)

    if log_type == LogType.SYNTH:
        path = pd / "fpga.runs" / "synth_1" / "runme.log"
        return path if path.exists() else None

    elif log_type == LogType.IMPL:
        path = pd / "fpga.runs" / "impl_1" / "runme.log"
        return path if path.exists() else None

    elif log_type == LogType.DAEMON:
        uid = os.getuid()
        path = Path("/tmp") / f"vproj-{uid}.log"
        return path if path.exists() else None

    elif log_type == LogType.SIM:
        # Find the most recent simulation log
        sim_dir = pd / "fpga.sim" / "sim_1"
        if not sim_dir.exists():
            return None
        # Look for simulate.log in any subdirectory
        logs = list(sim_dir.glob("*/simulate.log"))
        if not logs:
            return None
        # Return most recently modified
        return max(logs, key=lambda p: p.stat().st_mtime)

    return None


def extract_messages(
    log_path: Path,
    severities: Optional[set[Severity]] = None,
    grep_pattern: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Extract messages from a Vivado log file.

    Args:
        log_path: Path to the log file
        severities: Set of severity levels to include (None = all)
        grep_pattern: Regex pattern to filter messages (None = no filter)

    Returns:
        List of (severity, message) tuples
    """
    if not log_path.exists():
        return []

    messages = []
    # Match Vivado message format: WARNING: [Tag] message or ERROR: [Tag] message
    pattern = re.compile(r"^(WARNING|ERROR|CRITICAL WARNING):\s*(.+)$")

    grep_re = re.compile(grep_pattern, re.IGNORECASE) if grep_pattern else None

    for line in log_path.read_text().splitlines():
        match = pattern.match(line)
        if match:
            level, msg = match.groups()

            # Filter by severity
            if severities:
                if level not in severities:
                    continue

            # Filter by grep pattern (search both level and message)
            if grep_re and not (grep_re.search(level) or grep_re.search(msg)):
                continue

            messages.append((level, msg))

    return messages


def read_log_lines(
    log_path: Path,
    tail: Optional[int] = None,
    grep_pattern: Optional[str] = None,
) -> list[str]:
    """Read lines from a log file.

    Args:
        log_path: Path to the log file
        tail: If set, only return the last N lines
        grep_pattern: Regex pattern to filter lines (None = no filter)

    Returns:
        List of log lines
    """
    if not log_path.exists():
        return []

    lines = log_path.read_text().splitlines()

    # Filter by grep pattern
    if grep_pattern:
        grep_re = re.compile(grep_pattern, re.IGNORECASE)
        lines = [line for line in lines if grep_re.search(line)]

    # Tail
    if tail and len(lines) > tail:
        lines = lines[-tail:]

    return lines


def format_messages(
    messages: list[tuple[str, str]],
    no_color: bool = False,
) -> list[str]:
    """Format messages for display.

    Args:
        messages: List of (severity, message) tuples
        no_color: If True, don't use Rich markup

    Returns:
        List of formatted strings
    """
    from rich.markup import escape

    result = []
    for level, msg in messages:
        if no_color:
            result.append(f"{level}: {msg}")
        else:
            # Escape message content to prevent Rich markup interpretation
            escaped_msg = escape(msg)
            if level == "ERROR":
                result.append(f"[red]{level}:[/red] {escaped_msg}")
            elif level == "CRITICAL WARNING":
                result.append(f"[yellow]CRITICAL:[/yellow] {escaped_msg}")
            else:
                result.append(f"[dim]{level}:[/dim] {escaped_msg}")
    return result


def get_log_summary(
    proj_dir: Optional[Path] = None,
) -> dict[str, dict[str, int]]:
    """Get summary of warnings/errors from build logs.

    Args:
        proj_dir: Project directory

    Returns:
        Dict mapping log type to counts: {"synth": {"errors": 0, "warnings": 5, ...}, ...}
    """
    summary = {}

    for log_type in [LogType.SYNTH, LogType.IMPL]:
        log_path = get_log_path(log_type, proj_dir)
        if log_path:
            messages = extract_messages(log_path)
            errors = sum(1 for level, _ in messages if level == "ERROR")
            warnings = sum(1 for level, _ in messages if level == "WARNING")
            critical = sum(1 for level, _ in messages if level == "CRITICAL WARNING")
            summary[log_type.value] = {
                "errors": errors,
                "warnings": warnings,
                "critical_warnings": critical,
            }

    return summary
