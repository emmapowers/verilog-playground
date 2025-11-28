"""Vivado message query and management utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .vivado import (
    PROJECT_DIR_DEFAULT,
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
)


@dataclass
class MessageConfig:
    """Vivado message configuration state."""

    info_suppressed: bool = False
    warning_suppressed: bool = False
    error_suppressed: bool = False
    critical_suppressed: bool = False
    warning_count: int = 0
    error_count: int = 0
    critical_count: int = 0
    info_count: int = 0


def get_message_config(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> Optional[MessageConfig]:
    """Query Vivado message configuration and counts.

    Returns:
        MessageConfig with current state, or None on error
    """
    xpr = find_xpr(proj_hint, proj_dir)
    if not xpr:
        return None

    # TCL to query message config
    # Note: get_msg_config -rules returns rules, we check for suppress rules
    tcl = f"""
{make_smart_open(xpr)}

# Check suppression status by trying to get rules for each severity
# We'll check if -suppress is set by querying the config
proc check_suppressed {{severity}} {{
    set rules [get_msg_config -rules -severity $severity]
    foreach rule $rules {{
        if {{[string match "*suppress*" $rule]}} {{
            return 1
        }}
    }}
    return 0
}}

puts "INFO_SUPPRESSED|[check_suppressed INFO]"
puts "WARNING_SUPPRESSED|[check_suppressed WARNING]"
puts "ERROR_SUPPRESSED|[check_suppressed ERROR]"
puts "CRITICAL_SUPPRESSED|[check_suppressed {{CRITICAL WARNING}}]"

# Get message counts
puts "INFO_COUNT|[get_msg_config -count -severity INFO]"
puts "WARNING_COUNT|[get_msg_config -count -severity WARNING]"
puts "ERROR_COUNT|[get_msg_config -count -severity ERROR]"
puts "CRITICAL_COUNT|[get_msg_config -count -severity {{CRITICAL WARNING}}]"

{make_smart_close()}
"""

    result = run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir or Path(PROJECT_DIR_DEFAULT),
        settings=settings,
        quiet=True,
        batch=batch,
        gui=gui,
        daemon=daemon,
        return_output=True,
    )

    code, output = result
    if code != 0:
        return None

    # Parse output
    config = MessageConfig()
    for line in output.splitlines():
        if "|" in line:
            key, _, value = line.partition("|")
            key = key.strip()
            value = value.strip()

            if key == "INFO_SUPPRESSED":
                config.info_suppressed = value == "1"
            elif key == "WARNING_SUPPRESSED":
                config.warning_suppressed = value == "1"
            elif key == "ERROR_SUPPRESSED":
                config.error_suppressed = value == "1"
            elif key == "CRITICAL_SUPPRESSED":
                config.critical_suppressed = value == "1"
            elif key == "INFO_COUNT":
                config.info_count = int(value) if value.isdigit() else 0
            elif key == "WARNING_COUNT":
                config.warning_count = int(value) if value.isdigit() else 0
            elif key == "ERROR_COUNT":
                config.error_count = int(value) if value.isdigit() else 0
            elif key == "CRITICAL_COUNT":
                config.critical_count = int(value) if value.isdigit() else 0

    return config


def reset_message_config(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool = False,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Reset all message suppressions.

    Returns:
        Exit code (0 = success)
    """
    xpr = find_xpr(proj_hint, proj_dir)
    if not xpr:
        return 1

    tcl = f"""
{make_smart_open(xpr)}

# Reset all message suppressions
catch {{ reset_msg_config -suppress -severity {{WARNING}} }}
catch {{ reset_msg_config -suppress -severity {{INFO}} }}
catch {{ reset_msg_config -suppress -severity {{ERROR}} }}
catch {{ reset_msg_config -suppress -severity {{CRITICAL WARNING}} }}

{make_smart_close()}
"""

    result = run_vivado_tcl_auto(
        tcl,
        proj_dir=proj_dir or Path(PROJECT_DIR_DEFAULT),
        settings=settings,
        quiet=quiet,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )

    return result if isinstance(result, int) else result[0]
