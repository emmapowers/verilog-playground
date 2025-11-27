"""Vivado daemon management - persistent Vivado process for fast commands."""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple

import click

from .vivado import PROJECT_DIR_DEFAULT

# Daemon configuration
SOCKET_TIMEOUT = 5.0  # Connection timeout
COMMAND_TIMEOUT = 600.0  # 10 min for long builds


def _get_port_file(proj_dir: Optional[Path] = None) -> Path:
    """Get project-local port file path."""
    pd = proj_dir or Path(PROJECT_DIR_DEFAULT)
    return pd / ".vproj-port"


def _get_log_file() -> Path:
    """Get daemon log file path (user-global)."""
    uid = os.getuid()
    return Path("/tmp") / f"vproj-{uid}.log"


def _find_lock_file(proj_dir: Optional[Path] = None) -> Optional[Path]:
    """Find Vivado .xpr.lck file if project is locked by GUI."""
    pd = proj_dir or Path(PROJECT_DIR_DEFAULT)
    if not pd.exists():
        return None
    locks = list(pd.glob("*.xpr.lck"))
    return locks[0] if locks else None


def _get_server_tcl() -> Path:
    """Get path to server.tcl bundled with vproj."""
    return Path(__file__).parent / "server.tcl"


class ServerInfo:
    """Information about a running vproj server."""

    def __init__(
        self,
        running: bool,
        port: Optional[int] = None,
        is_gui: bool = False,
        proj_dir: Optional[Path] = None,
    ):
        self.running = running
        self.port = port
        self.is_gui = is_gui
        self.proj_dir = proj_dir


def find_server(proj_dir: Optional[Path] = None) -> ServerInfo:
    """
    Find a running vproj server (daemon or GUI).

    Args:
        proj_dir: Project directory to check

    Returns:
        ServerInfo with details about the server
    """
    pd = Path(proj_dir) if proj_dir else Path(PROJECT_DIR_DEFAULT)
    port_file = _get_port_file(pd)
    lock_file = _find_lock_file(pd)

    # Check if port file exists
    if not port_file.exists():
        return ServerInfo(running=False, is_gui=lock_file is not None, proj_dir=pd)

    try:
        port = int(port_file.read_text().strip())
    except (ValueError, OSError):
        return ServerInfo(running=False, is_gui=lock_file is not None, proj_dir=pd)

    # Try to ping the server
    try:
        result = _send_tcl_to_port(port, "PING", timeout=2.0)
        if "PONG" in result:
            return ServerInfo(
                running=True,
                port=port,
                is_gui=lock_file is not None,
                proj_dir=pd,
            )
    except Exception:
        # Server not responding, clean up stale port file
        try:
            port_file.unlink(missing_ok=True)
        except Exception:
            pass

    return ServerInfo(running=False, is_gui=lock_file is not None, proj_dir=pd)


def daemon_status(proj_dir: Optional[Path] = None) -> Tuple[bool, Optional[int], bool]:
    """
    Check if daemon/server is running.

    Returns:
        (is_running, port, is_gui)
    """
    info = find_server(proj_dir)
    return info.running, info.port, info.is_gui


def _cleanup_files(proj_dir: Optional[Path] = None):
    """Remove daemon port file."""
    port_file = _get_port_file(proj_dir)
    try:
        port_file.unlink(missing_ok=True)
    except Exception:
        pass


def start_daemon(
    proj_dir: Optional[Path] = None,
    settings: Optional[Path] = None,
    quiet: bool = False,
) -> bool:
    """
    Start the Vivado daemon.

    Args:
        proj_dir: Project directory for port file
        settings: Path to Vivado settings64.sh (optional if vivado in PATH)
        quiet: Suppress output

    Returns:
        True if started successfully
    """
    pd = Path(proj_dir) if proj_dir else Path(PROJECT_DIR_DEFAULT)

    info = find_server(pd)
    if info.running:
        if not quiet:
            click.echo(f"Server already running (port {info.port})")
        return True

    # Check if GUI has lock but no server
    if info.is_gui:
        server_tcl = _get_server_tcl()
        raise click.ClickException(
            "Vivado GUI has the project locked but server not running.\n"
            "To enable vproj commands in GUI mode, run this in the Vivado TCL console:\n"
            f"  source {server_tcl}\n\n"
            "Or install permanently:\n"
            "  vproj server install"
        )

    # Clean up any stale files
    _cleanup_files(pd)

    # Ensure project directory exists
    pd.mkdir(parents=True, exist_ok=True)

    port_file = _get_port_file(pd)
    log_file = _get_log_file()
    server_tcl = _get_server_tcl()

    if not server_tcl.exists():
        raise click.ClickException(f"Server script not found: {server_tcl}")

    # Build the vivado command (server.tcl will find its own port)
    vivado_cmd = (
        f"vivado -mode tcl -nolog -nojournal "
        f"-source {shlex.quote(str(server_tcl))} "
        f"-tclargs {shlex.quote(str(pd.resolve()))}"
    )

    if settings:
        full_cmd = f"source {shlex.quote(str(settings))} && {vivado_cmd}"
        cmd = ["bash", "-lc", full_cmd]
    else:
        if shutil.which("vivado") is None:
            _cleanup_files(pd)
            raise click.ClickException(
                "Vivado not found in PATH. Either:\n"
                "  1. Source Vivado settings first\n"
                "  2. Pass --settings /path/to/settings64.sh"
            )
        cmd = ["bash", "-c", vivado_cmd]

    if not quiet:
        click.echo("Starting Vivado daemon...")

    # Start Vivado in background
    with open(log_file, "w") as log:
        subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # Detach from terminal
        )

    # Wait for daemon to start (poll for port file and connectivity)
    for _ in range(60):  # Wait up to 60 seconds
        time.sleep(1)
        if port_file.exists():
            try:
                port = int(port_file.read_text().strip())
                result = _send_tcl_to_port(port, "PING", timeout=2.0)
                if "PONG" in result:
                    if not quiet:
                        click.echo(f"Daemon started (port {port})")
                    return True
            except Exception:
                pass

    # Failed to start
    _cleanup_files(pd)
    if not quiet:
        click.echo(f"Failed to start daemon. Check log: {log_file}", err=True)
    return False


def stop_daemon(proj_dir: Optional[Path] = None, quiet: bool = False) -> bool:
    """
    Stop the Vivado daemon.

    Returns:
        True if stopped successfully
    """
    pd = Path(proj_dir) if proj_dir else Path(PROJECT_DIR_DEFAULT)

    info = find_server(pd)
    if not info.running:
        if not quiet:
            click.echo("Server not running")
        _cleanup_files(pd)
        return True

    if not quiet:
        click.echo(f"Stopping server (port {info.port})...")

    # Try graceful shutdown
    try:
        _send_tcl_to_port(info.port, "QUIT", timeout=5.0)
        time.sleep(0.5)
    except Exception:
        pass

    _cleanup_files(pd)
    if not quiet:
        click.echo("Server stopped")
    return True


def _send_tcl_to_port(port: int, tcl: str, timeout: float = COMMAND_TIMEOUT) -> str:
    """
    Send TCL command to a specific port and return result.

    Args:
        port: TCP port to connect to
        tcl: TCL code to execute
        timeout: Timeout in seconds

    Returns:
        Command output

    Raises:
        Exception if connection fails or command fails
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect(("127.0.0.1", port))

        # Send command
        for line in tcl.split("\n"):
            sock.sendall((line + "\n").encode())
        sock.sendall(b"END_CMD\n")

        # Read response
        response_lines = []
        buffer = b""
        status = None

        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk

            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                # Strip CR if server sends CRLF
                line_str = line.decode("utf-8", errors="replace").rstrip("\r")

                if line_str == "END_RESPONSE":
                    if status == "ERROR":
                        raise RuntimeError("\n".join(response_lines))
                    return "\n".join(response_lines)
                elif line_str == "OK":
                    status = "OK"
                elif line_str == "ERROR":
                    status = "ERROR"
                else:
                    response_lines.append(line_str)

        # If we get here without END_RESPONSE, something went wrong
        if status == "ERROR":
            raise RuntimeError("\n".join(response_lines))
        return "\n".join(response_lines)

    finally:
        sock.close()


def send_tcl(
    tcl: str,
    proj_dir: Optional[Path] = None,
    timeout: float = COMMAND_TIMEOUT,
) -> str:
    """
    Send TCL command to server and return result.

    Args:
        tcl: TCL code to execute
        proj_dir: Project directory
        timeout: Timeout in seconds

    Returns:
        Command output

    Raises:
        Exception if server not running or command fails
    """
    info = find_server(proj_dir)

    if not info.running:
        raise RuntimeError("Server not running")

    return _send_tcl_to_port(info.port, tcl, timeout)


def is_server_available(proj_dir: Optional[Path] = None) -> bool:
    """Check if server is available for use."""
    info = find_server(proj_dir)
    return info.running


def get_server_script_path() -> Path:
    """Get path to server.tcl for manual sourcing in GUI."""
    return _get_server_tcl()


def get_vivado_init_path() -> Path:
    """Get path to Vivado init.tcl file."""
    return Path.home() / ".Xilinx" / "Vivado" / "Vivado_init.tcl"


def install_server_to_init() -> bool:
    """
    Install server auto-start to Vivado_init.tcl.

    Returns:
        True if installed successfully
    """
    init_file = get_vivado_init_path()
    server_tcl = _get_server_tcl()

    # Create directory if needed
    init_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if already installed
    marker = "# vproj server auto-start"
    if init_file.exists():
        content = init_file.read_text()
        if marker in content:
            return True  # Already installed
    else:
        content = ""

    # Add server auto-start
    snippet = f"""
{marker}
if {{[info exists ::env(VPROJ_NO_SERVER)] && $::env(VPROJ_NO_SERVER)}} {{
    # Server disabled via environment
}} else {{
    # Auto-start vproj server if project directory exists
    catch {{
        set _vproj_pd [pwd]
        if {{[file exists "$_vproj_pd/.vproj-port"]}} {{
            # Port file exists, server might be running elsewhere
        }} else {{
            set ::vproj_proj_dir $_vproj_pd
            source {server_tcl}
        }}
    }}
}}
"""

    init_file.write_text(content + snippet)
    return True


def uninstall_server_from_init() -> bool:
    """
    Remove server auto-start from Vivado_init.tcl.

    Returns:
        True if uninstalled successfully
    """
    init_file = get_vivado_init_path()

    if not init_file.exists():
        return True

    content = init_file.read_text()
    marker = "# vproj server auto-start"

    if marker not in content:
        return True  # Not installed

    # Remove the vproj section
    import re
    pattern = rf"\n{re.escape(marker)}.*?(?=\n# [^\n]|\Z)"
    content = re.sub(pattern, "", content, flags=re.DOTALL)

    init_file.write_text(content)
    return True
