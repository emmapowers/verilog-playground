"""Simulation and syntax checking commands."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple

import click

from .vivado import (
    PROJECT_DIR_DEFAULT,
    find_xpr,
    make_smart_close,
    make_smart_open,
    run_vivado_tcl_auto,
    tcl_quote,
)


def _find_tool(name: str) -> Optional[Path]:
    """Find a tool in PATH."""
    path = shutil.which(name)
    return Path(path) if path else None


def _get_project_sources(
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    include_sim: bool = True,
) -> List[Path]:
    """Get list of source files from project (requires Vivado)."""
    # This would need to parse Vivado output - for now return empty
    # and let the caller handle it
    return []


def check_cmd(
    files: Optional[tuple],
    use_verilator: bool,
    use_iverilog: bool,
    include_dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Fast syntax/lint check without full build.

    Default: verilator --lint-only (very fast)
    Fallback: iverilog -t null
    """
    # Determine which tool to use
    if use_verilator:
        tool = "verilator"
    elif use_iverilog:
        tool = "iverilog"
    else:
        # Auto-detect: prefer verilator for speed
        if _find_tool("verilator"):
            tool = "verilator"
        elif _find_tool("iverilog"):
            tool = "iverilog"
        else:
            raise click.ClickException(
                "No linting tool found. Install verilator or iverilog.\n"
                "  Ubuntu: sudo apt install verilator\n"
                "  Or: sudo apt install iverilog"
            )

    # Get files to check
    if files:
        file_list = [Path(f) for f in files]
    else:
        # Get all .v/.sv files from project directory
        pd = proj_dir or Path(PROJECT_DIR_DEFAULT)
        # Look in common source locations
        file_list = []
        for pattern in ["**/*.sv", "**/*.v"]:
            file_list.extend(Path(".").glob(pattern))
        # Filter out testbenches for syntax check by default
        file_list = [f for f in file_list if "tb" not in f.stem.lower() and "test" not in f.stem.lower()]

    if not file_list:
        raise click.ClickException("No source files found to check.")

    # Get include directories from project + CLI overrides
    all_includes: List[Path] = []

    # Try to get includes from project
    try:
        from .project import get_include_dirs
        project_includes = get_include_dirs(
            proj_hint, proj_dir, settings,
            batch=batch, gui=gui, daemon=daemon
        )
        all_includes.extend(project_includes)
    except Exception:
        # Project not available or error - continue without project includes
        pass

    # Add CLI-specified includes
    all_includes.extend(include_dirs)

    file_args = [str(f.resolve()) for f in file_list]

    if not quiet:
        click.echo(f"==> Checking {len(file_list)} files with {tool}")
        if all_includes:
            click.echo(f"    Include paths: {len(all_includes)}")

    # Build command with include paths
    # Note: verilator requires -Ipath format (no space), iverilog accepts both
    if tool == "verilator":
        cmd = ["verilator", "--lint-only", "-Wall", "--timing"]
        for inc in all_includes:
            cmd.append(f"-I{inc}")
        cmd.extend(file_args)
    else:  # iverilog
        cmd = ["iverilog", "-t", "null", "-g2012"]
        for inc in all_includes:
            cmd.append(f"-I{inc}")
        cmd.extend(file_args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.stdout and not quiet:
            click.echo(result.stdout)
        if result.stderr:
            # Verilator/iverilog output warnings/errors to stderr
            click.echo(result.stderr, err=True)

        if result.returncode == 0:
            if not quiet:
                click.echo("==> Check passed")
        else:
            if not quiet:
                click.echo("==> Check failed", err=True)

        return result.returncode

    except FileNotFoundError:
        raise click.ClickException(f"{tool} not found in PATH")


def sim_cmd(
    testbench: Path,
    use_xsim: bool,
    use_iverilog: bool,
    use_verilator: bool,
    use_fst: bool,
    output: Optional[Path],
    include_dirs: Tuple[Path, ...],
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool = False,
    gui: bool = False,
    daemon: bool = False,
) -> int:
    """Run simulation and generate waveform.

    Backends:
    - xsim (default): Vivado's simulator
    - iverilog: Icarus Verilog
    - verilator: Fast Verilog simulator
    """
    pd = proj_dir or Path(PROJECT_DIR_DEFAULT)
    sim_dir = pd / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)

    tb_name = testbench.stem
    ext = ".fst" if use_fst else ".vcd"
    out_file = output or (sim_dir / f"{tb_name}{ext}")

    # Determine backend
    if use_xsim:
        backend = "xsim"
    elif use_iverilog:
        backend = "iverilog"
    elif use_verilator:
        backend = "verilator"
    else:
        # Default to xsim if we have Vivado, else iverilog
        backend = "xsim"

    # Get include directories from project + CLI overrides
    all_includes: List[Path] = []

    # For non-xsim backends, get includes from project
    if backend != "xsim":
        try:
            from .project import get_include_dirs
            project_includes = get_include_dirs(
                proj_hint, proj_dir, settings,
                batch=batch, gui=gui, daemon=daemon
            )
            all_includes.extend(project_includes)
        except Exception:
            pass

    # Add CLI-specified includes
    all_includes.extend(include_dirs)

    if not quiet:
        click.echo(f"==> Running simulation with {backend}")
        click.echo(f"    Testbench: {testbench}")
        click.echo(f"    Output: {out_file}")
        if all_includes and backend != "xsim":
            click.echo(f"    Include paths: {len(all_includes)}")

    if backend == "xsim":
        return _sim_xsim(
            testbench, out_file, proj_hint, proj_dir, settings, quiet,
            batch=batch, gui=gui, daemon=daemon
        )
    elif backend == "iverilog":
        return _sim_iverilog(testbench, out_file, use_fst, all_includes, proj_dir, quiet)
    else:
        return _sim_verilator(testbench, out_file, all_includes, proj_dir, quiet)


def _sim_xsim(
    testbench: Path,
    output: Path,
    proj_hint: Optional[Path],
    proj_dir: Optional[Path],
    settings: Optional[Path],
    quiet: bool,
    batch: bool,
    gui: bool,
    daemon: bool,
) -> int:
    """Run simulation with Vivado xsim."""
    xpr = find_xpr(proj_hint, proj_dir)
    tb_name = testbench.stem

    tcl = make_smart_open(xpr) + f"""
# Set testbench as top for simulation
set_property top {tb_name} [get_filesets sim_1]
update_compile_order -fileset sim_1

# Launch simulation
launch_simulation

# Run until completion
run all

# Export waveform
# Note: xsim waveform is in the project sim directory
puts "Simulation complete"
puts "Waveform available in project sim directory"

close_sim
""" + make_smart_close()

    return run_vivado_tcl_auto(
        tcl, proj_dir=proj_dir, settings=settings, quiet=quiet,
        batch=batch, gui=gui, daemon=daemon
    )


def _sim_iverilog(
    testbench: Path,
    output: Path,
    use_fst: bool,
    include_dirs: List[Path],
    proj_dir: Optional[Path],
    quiet: bool,
) -> int:
    """Run simulation with Icarus Verilog."""
    if not _find_tool("iverilog"):
        raise click.ClickException("iverilog not found. Install with: sudo apt install iverilog")

    # Gather source files
    sources = []
    for pattern in ["**/*.sv", "**/*.v"]:
        sources.extend(Path(".").glob(pattern))

    if not sources:
        raise click.ClickException("No source files found")

    # Create temp directory for build
    with tempfile.TemporaryDirectory() as tmpdir:
        sim_out = Path(tmpdir) / "sim.out"
        tb_name = testbench.stem

        # Compile with include paths
        compile_cmd = [
            "iverilog",
            "-g2012",
            "-o", str(sim_out),
            "-s", tb_name,
        ]
        for inc in include_dirs:
            compile_cmd.append(f"-I{inc}")
        compile_cmd.extend([str(f) for f in sources])

        if not quiet:
            click.echo(f"Compiling: {' '.join(compile_cmd[:6])}...")

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(result.stderr, err=True)
            return result.returncode

        # Run simulation
        vvp_cmd = ["vvp", str(sim_out)]
        if use_fst:
            vvp_cmd.append("-fst")

        env = {"VCD_FILE": str(output.resolve())}

        if not quiet:
            click.echo("Running simulation...")

        result = subprocess.run(
            vvp_cmd,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
        )

        if result.stdout and not quiet:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        if result.returncode == 0 and not quiet:
            click.echo(f"==> Waveform: {output}")

        return result.returncode


def _sim_verilator(
    testbench: Path,
    output: Path,
    include_dirs: List[Path],
    proj_dir: Optional[Path],
    quiet: bool,
) -> int:
    """Run simulation with Verilator."""
    if not _find_tool("verilator"):
        raise click.ClickException("verilator not found. Install with: sudo apt install verilator")

    # Gather source files
    sources = []
    for pattern in ["**/*.sv", "**/*.v"]:
        sources.extend(Path(".").glob(pattern))

    if not sources:
        raise click.ClickException("No source files found")

    tb_name = testbench.stem

    with tempfile.TemporaryDirectory() as tmpdir:
        # Compile with verilator and include paths
        compile_cmd = [
            "verilator",
            "--binary",
            "--trace",
            "-j", "0",
            "-Wall",
            "-Wno-fatal",
            "--timing",
            "--top", tb_name,
            "-Mdir", tmpdir,
        ]
        for inc in include_dirs:
            compile_cmd.append(f"-I{inc}")
        compile_cmd.extend([str(f) for f in sources])

        if not quiet:
            click.echo("Compiling with verilator...")

        result = subprocess.run(compile_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(result.stderr, err=True)
            return result.returncode

        # Run simulation
        exe = Path(tmpdir) / f"V{tb_name}"
        if not exe.exists():
            raise click.ClickException(f"Verilator executable not found: {exe}")

        if not quiet:
            click.echo("Running simulation...")

        result = subprocess.run(
            [str(exe)],
            capture_output=True,
            text=True,
            cwd=tmpdir,
        )

        if result.stdout and not quiet:
            click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr, err=True)

        # Move trace file
        trace = Path(tmpdir) / "trace.vcd"
        if trace.exists():
            shutil.move(str(trace), str(output))
            if not quiet:
                click.echo(f"==> Waveform: {output}")

        return result.returncode


__all__ = ["sim_cmd", "check_cmd"]
