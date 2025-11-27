"""Main CLI entry point for vproj."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .vivado import PROJECT_DIR_DEFAULT, check_vivado_available
from .project import (
    list_cmd,
    add_src_cmd,
    add_xdc_cmd,
    add_sim_cmd,
    add_ip_cmd,
    remove_cmd,
    mv_cmd,
)
from .tcl_export import export_tcl_cmd
from .tcl_import import import_tcl_cmd
from .build import build_cmd
from .program import program_cmd
from .clean import clean_cmd


@click.group(context_settings=dict(help_option_names=["-h", "--help"]))
@click.option(
    "--proj",
    "proj_hint",
    type=click.Path(path_type=Path),
    required=False,
    help="Path to .xpr OR a directory to search. If omitted, search current dir.",
)
@click.option(
    "--settings",
    type=click.Path(path_type=Path, exists=True),
    help="settings64.sh to source before invoking Vivado.",
)
@click.option("-q", "--quiet", is_flag=True, help="Suppress Vivado stdout.")
@click.option(
    "--proj-dir",
    type=click.Path(path_type=Path),
    default=PROJECT_DIR_DEFAULT,
    show_default=True,
    help="Directory where the Vivado project (.xpr) lives.",
)
@click.option(
    "--batch",
    is_flag=True,
    help="Force batch mode (slow, no server).",
)
@click.option(
    "--gui",
    is_flag=True,
    help="Force GUI mode (require existing Vivado GUI with server).",
)
@click.option(
    "--daemon",
    is_flag=True,
    help="Force daemon mode (start daemon if not running).",
)
@click.pass_context
def cli(
    ctx,
    proj_hint: Optional[Path],
    settings: Optional[Path],
    proj_dir: Optional[Path],
    quiet: bool,
    batch: bool,
    gui: bool,
    daemon: bool,
):
    """Manage Vivado projects without the GUI."""
    ctx.ensure_object(dict)
    ctx.obj.update(
        settings=settings,
        quiet=quiet,
        proj_hint=proj_hint,
        proj_dir=proj_dir,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )


# --- File listing ---


@cli.command("list")
@click.pass_context
def list_(ctx):
    """List files in sources_1, constrs_1, and sim_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        list_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# Alias: ls -> list
@cli.command("ls")
@click.pass_context
def ls_(ctx):
    """List files in project (alias for 'list')."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        list_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Add commands ---


@cli.command("add-src")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.pass_context
def add_src(ctx, files):
    """Add HDL source files (.v, .sv, .vhd) to sources_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        add_src_cmd(
            files,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@cli.command("add-xdc")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.pass_context
def add_xdc(ctx, files):
    """Add constraint files (.xdc) to constrs_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        add_xdc_cmd(
            files,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@cli.command("add-sim")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.pass_context
def add_sim(ctx, files):
    """Add testbench files to sim_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        add_sim_cmd(
            files,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@cli.command("add-ip")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.pass_context
def add_ip(ctx, files):
    """Add IP files (.xci, .bd) to sources_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        add_ip_cmd(
            files,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Remove command ---


@cli.command("remove")
@click.argument("files", type=click.Path(path_type=Path), nargs=-1, required=True)
@click.option("-r", "--recursive", is_flag=True, help="Remove folder contents recursively.")
@click.pass_context
def remove(ctx, files, recursive):
    """Remove files from project (does NOT delete from disk)."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        remove_cmd(
            files,
            recursive,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# Alias: rm -> remove
@cli.command("rm")
@click.argument("files", type=click.Path(path_type=Path), nargs=-1, required=True)
@click.option("-r", "--recursive", is_flag=True, help="Remove folder contents recursively.")
@click.pass_context
def rm_(ctx, files, recursive):
    """Remove files from project (alias for 'remove')."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        remove_cmd(
            files,
            recursive,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Move command ---


@cli.command("mv")
@click.argument("old", type=click.Path(path_type=Path))
@click.argument("new", type=click.Path(path_type=Path))
@click.option("-r", "--recursive", is_flag=True, help="Move folder contents recursively.")
@click.pass_context
def mv_(ctx, old, new, recursive):
    """Move/rename file or folder (disk + project)."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        mv_cmd(
            old,
            new,
            recursive,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- TCL export/import ---


@cli.command("export-tcl")
@click.option(
    "--out",
    "out_tcl",
    type=click.Path(path_type=Path),
    default=Path("project.tcl"),
    show_default=True,
)
@click.option(
    "--rel-to",
    "rel_to",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
)
@click.option("--no-copy-sources", is_flag=True)
@click.option("--keep-dcp", is_flag=True)
@click.pass_context
def export_tcl(ctx, out_tcl, rel_to, no_copy_sources, keep_dcp):
    """Export project to a TCL script."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        export_tcl_cmd(
            out_tcl,
            rel_to,
            no_copy_sources,
            keep_dcp,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@cli.command("import-tcl")
@click.argument("project_tcl", type=click.Path(path_type=Path, exists=True))
@click.option("--workdir", type=click.Path(path_type=Path), help="cd before sourcing TCL.")
@click.option("--force", is_flag=True, help="Overwrite existing project.")
@click.option("--wipe", is_flag=True, help="Delete proj-dir before import.")
@click.pass_context
def import_tcl(ctx, project_tcl, workdir, force, wipe):
    """Import project from a TCL script."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        import_tcl_cmd(
            project_tcl,
            workdir,
            force,
            wipe,
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Build command ---


@cli.command("build")
@click.option("-j", "--jobs", type=int, default=8, show_default=True, help="Parallel jobs.")
@click.option("--force", is_flag=True, help="Force full rebuild (reset runs).")
@click.option("--synth-only", is_flag=True, help="Stop after synthesis.")
@click.option("--no-bit", is_flag=True, help="Skip bitstream generation.")
@click.pass_context
def build(ctx, jobs, force, synth_only, no_bit):
    """Build bitstream (synthesis + implementation)."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        build_cmd(
            jobs,
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
            force=force,
            synth_only=synth_only,
            no_bit=no_bit,
        )
    )


# --- Program command ---


@cli.command("program")
@click.argument("bitfile", type=click.Path(path_type=Path, exists=True), required=False)
@click.pass_context
def program(ctx, bitfile):
    """Program FPGA over JTAG."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        program_cmd(
            bitfile,
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Clean command ---


@cli.command("clean")
@click.pass_context
def clean(ctx):
    """Remove Vivado build artifacts."""
    raise SystemExit(clean_cmd(ctx.obj["quiet"]))


# --- Simulation commands ---


@cli.command("sim")
@click.argument("testbench", type=click.Path(path_type=Path, exists=True))
@click.option("--xsim", "use_xsim", is_flag=True, help="Use Vivado xsim (default).")
@click.option("--iverilog", "use_iverilog", is_flag=True, help="Use Icarus Verilog.")
@click.option("--verilator", "use_verilator", is_flag=True, help="Use Verilator.")
@click.option("--fst", "use_fst", is_flag=True, help="Output FST instead of VCD.")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output waveform path.")
@click.option("-I", "--include", "include_dirs", multiple=True,
              type=click.Path(path_type=Path, exists=True),
              help="Add include directory (can specify multiple times).")
@click.pass_context
def sim(ctx, testbench, use_xsim, use_iverilog, use_verilator, use_fst, output, include_dirs):
    """Run simulation and generate waveform."""
    from .sim import sim_cmd

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        sim_cmd(
            testbench,
            use_xsim,
            use_iverilog,
            use_verilator,
            use_fst,
            output,
            include_dirs,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@cli.command("check")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1)
@click.option("--verilator", "use_verilator", is_flag=True, help="Use Verilator (default).")
@click.option("--iverilog", "use_iverilog", is_flag=True, help="Use Icarus Verilog.")
@click.option("-I", "--include", "include_dirs", multiple=True,
              type=click.Path(path_type=Path, exists=True),
              help="Add include directory (can specify multiple times).")
@click.pass_context
def check(ctx, files, use_verilator, use_iverilog, include_dirs):
    """Fast syntax/lint check (uses project include paths)."""
    from .sim import check_cmd

    raise SystemExit(
        check_cmd(
            files,
            use_verilator,
            use_iverilog,
            include_dirs,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Include path commands ---


@cli.group("include")
def include():
    """Manage include directories for the project."""
    pass


@include.command("list")
@click.pass_context
def include_list(ctx):
    """List include directories in the project."""
    from .project import include_list_cmd

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        include_list_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@include.command("add")
@click.argument("dirs", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@click.pass_context
def include_add(ctx, dirs):
    """Add include directories to the project."""
    from .project import include_add_cmd

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        include_add_cmd(
            dirs,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@include.command("rm")
@click.argument("dirs", type=click.Path(path_type=Path), nargs=-1, required=True)
@click.pass_context
def include_rm(ctx, dirs):
    """Remove include directories from the project."""
    from .project import include_rm_cmd

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        include_rm_cmd(
            dirs,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Server commands ---


@cli.group("server")
def server():
    """Manage the Vivado server for faster commands."""
    pass


@server.command("start")
@click.pass_context
def server_start(ctx):
    """Start the Vivado daemon server."""
    from .daemon import start_daemon

    try:
        success = start_daemon(
            proj_dir=ctx.obj["proj_dir"],
            settings=ctx.obj["settings"],
            quiet=ctx.obj["quiet"],
        )
        raise SystemExit(0 if success else 1)
    except click.ClickException as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@server.command("stop")
@click.pass_context
def server_stop(ctx):
    """Stop the Vivado server."""
    from .daemon import stop_daemon

    success = stop_daemon(proj_dir=ctx.obj["proj_dir"], quiet=ctx.obj["quiet"])
    raise SystemExit(0 if success else 1)


@server.command("status")
@click.pass_context
def server_status_cmd(ctx):
    """Check if the Vivado server is running."""
    from .daemon import find_server

    info = find_server(ctx.obj["proj_dir"])
    if info.running:
        mode = "GUI" if info.is_gui else "daemon"
        click.echo(f"Server running ({mode} mode, port {info.port})")
        raise SystemExit(0)
    elif info.is_gui:
        click.echo("GUI detected but server not running")
        raise SystemExit(1)
    else:
        click.echo("Server not running")
        raise SystemExit(1)


@server.command("install")
@click.pass_context
def server_install(ctx):
    """Install server auto-start to Vivado_init.tcl."""
    from .daemon import install_server_to_init, get_vivado_init_path

    if install_server_to_init():
        click.echo(f"Server installed to {get_vivado_init_path()}")
        click.echo("The vproj server will auto-start with Vivado.")
        raise SystemExit(0)
    else:
        click.echo("Failed to install server", err=True)
        raise SystemExit(1)


@server.command("uninstall")
@click.pass_context
def server_uninstall(ctx):
    """Remove server auto-start from Vivado_init.tcl."""
    from .daemon import uninstall_server_from_init

    if uninstall_server_from_init():
        click.echo("Server uninstalled from Vivado_init.tcl")
        raise SystemExit(0)
    else:
        click.echo("Failed to uninstall server", err=True)
        raise SystemExit(1)


@server.command("script")
@click.pass_context
def server_script(ctx):
    """Print TCL to paste in Vivado GUI console."""
    from .daemon import get_server_script_path

    script_path = get_server_script_path()
    click.echo("Paste this in the Vivado TCL console to enable vproj commands:\n")
    click.echo(f"  source {script_path}")
    click.echo("\nOr install permanently with: vproj server install")


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
