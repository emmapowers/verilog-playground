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
    get_top_module,
    set_top_module,
    get_hierarchy,
)
from .tcl_export import export_tcl_cmd
from .tcl_import import import_tcl_cmd
from .build import build_cmd
from .program import program_cmd
from .clean import clean_cmd


# Command categories for help formatting
COMMAND_CATEGORIES = {
    "Project": ["ls", "top", "tree", "add-src", "add-xdc", "add-sim", "add-ip", "rm", "mv", "include"],
    "Build": ["build", "program", "clean"],
    "Verify": ["check", "lint", "sim"],
    "TCL": ["export-tcl", "import-tcl"],
    "Server": ["server"],
}


class CategorizedGroup(click.Group):
    """Click group with categorized command listing in help."""

    def format_commands(self, ctx, formatter):
        """Format commands by category."""
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            commands.append((subcommand, cmd))

        if not commands:
            return

        # Build category -> commands mapping
        categorized = {cat: [] for cat in COMMAND_CATEGORIES}
        uncategorized = []

        for subcommand, cmd in commands:
            help_text = cmd.get_short_help_str(limit=formatter.width)
            found = False
            for cat, cat_commands in COMMAND_CATEGORIES.items():
                if subcommand in cat_commands:
                    categorized[cat].append((subcommand, help_text))
                    found = True
                    break
            if not found:
                uncategorized.append((subcommand, help_text))

        # Write categories
        for cat, cat_commands in categorized.items():
            if cat_commands:
                with formatter.section(cat):
                    formatter.write_dl(cat_commands)

        if uncategorized:
            with formatter.section("Other"):
                formatter.write_dl(uncategorized)


@click.group(cls=CategorizedGroup, context_settings=dict(help_option_names=["-h", "--help"]))
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
@click.option("--no-color", is_flag=True, help="Disable colored output.")
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
    no_color: bool,
    batch: bool,
    gui: bool,
    daemon: bool,
):
    """Manage Vivado projects without the GUI."""
    ctx.ensure_object(dict)
    ctx.obj.update(
        settings=settings,
        quiet=quiet,
        no_color=no_color,
        proj_hint=proj_hint,
        proj_dir=proj_dir,
        batch=batch,
        gui=gui,
        daemon=daemon,
    )


# --- File listing ---


def _relative_path(path: str) -> str:
    """Convert absolute path to relative path from current working directory."""
    try:
        return str(Path(path).relative_to(Path.cwd()))
    except ValueError:
        # Path is not relative to cwd, return as-is
        return path


@cli.command("ls")
@click.pass_context
def ls_(ctx):
    """List files in sources_1, constrs_1, and sim_1."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    no_color = ctx.obj.get("no_color", False)

    # Get top module to highlight it
    top_module = get_top_module(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )

    if no_color:
        # Plain output mode
        files = list_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
            return_data=True,
        )

        if isinstance(files, int):
            raise SystemExit(files)

        for fileset, path, ftype in files:
            # Check if this file contains the top module
            filename = Path(path).stem
            rel_path = _relative_path(path)
            marker = " [TOP]" if top_module and filename == top_module else ""
            click.echo(f"{fileset}\t{rel_path}\t{ftype}{marker}")

        raise SystemExit(0)
    else:
        # Rich table output
        from rich.console import Console
        from rich.table import Table

        files = list_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
            return_data=True,
        )

        if isinstance(files, int):
            # Error occurred
            raise SystemExit(files)

        console = Console()
        table = Table(show_header=True)
        table.add_column("Fileset", style="cyan")
        table.add_column("File")
        table.add_column("Type", style="dim")

        for fileset, path, ftype in files:
            # Check if this file contains the top module
            filename = Path(path).stem
            rel_path = _relative_path(path)
            if top_module and filename == top_module:
                # Highlight the top module file with marker at start
                table.add_row(f"[bold green]{fileset}[/bold green]", f"[bold green]{rel_path}[/bold green]", f"[bold green]{ftype} *[/bold green]")
            else:
                table.add_row(fileset, rel_path, ftype)

        console.print(table)
        raise SystemExit(0)


@cli.command("top")
@click.argument("module", required=False)
@click.pass_context
def top_(ctx, module):
    """Get or set the top module.

    With no argument, prints the current top module.
    With MODULE argument, sets it as the new top module.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    if module is None:
        # Get current top module
        top = get_top_module(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
        if top:
            click.echo(top)
            raise SystemExit(0)
        else:
            click.echo("No top module set", err=True)
            raise SystemExit(1)
    else:
        # Set top module
        raise SystemExit(
            set_top_module(
                module,
                ctx.obj["proj_hint"],
                ctx.obj["proj_dir"],
                ctx.obj["settings"],
                ctx.obj["quiet"],
                batch=ctx.obj["batch"],
                gui=ctx.obj["gui"],
                daemon=ctx.obj["daemon"],
            )
        )


@cli.command("tree")
@click.option("--nets", is_flag=True, help="Include all nets/primitives (verbose).")
@click.pass_context
def tree_(ctx, nets):
    """Show module instantiation hierarchy.

    Elaborates the design and shows which modules instantiate which.
    Use --nets to include all nets and primitives.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    from rich.console import Console
    from rich.tree import Tree

    # Get hierarchy data
    cells = get_hierarchy(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
        include_nets=nets,
    )

    if not cells:
        click.echo("Could not get module hierarchy (elaboration may have failed)", err=True)
        raise SystemExit(1)

    # Get top module
    top_module = get_top_module(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )

    # Build hierarchy tree
    # cells is list of (instance_name, parent, module_type)
    # Build parent->children mapping
    children: dict[str, list[tuple[str, str]]] = {}  # parent -> [(instance, module_type)]
    for instance, parent, module_type in cells:
        if parent not in children:
            children[parent] = []
        children[parent].append((instance, module_type))

    console = Console()

    # Create rich tree
    tree = Tree(f"[bold]{top_module or 'top'}[/bold]")

    def add_children(tree_node, parent_path: str):
        """Recursively add children to tree."""
        if parent_path in children:
            for instance, module_type in sorted(children[parent_path]):
                child_path = f"{parent_path}/{instance}" if parent_path else instance
                # Format: instance_name (module_type)
                label = f"{instance} [dim]({module_type})[/dim]"
                child_node = tree_node.add(label)
                add_children(child_node, child_path)

    # Start from empty parent (top-level instances)
    add_children(tree, "")

    console.print(tree)
    raise SystemExit(0)


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


@cli.command("rm")
@click.argument("files", type=click.Path(path_type=Path), nargs=-1, required=True)
@click.option("-r", "--recursive", is_flag=True, help="Remove folder contents recursively.")
@click.pass_context
def rm_(ctx, files, recursive):
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
@click.option("--program", "do_program", is_flag=True, help="Program FPGA after build.")
@click.pass_context
def build(ctx, jobs, force, synth_only, no_bit, do_program):
    """Build bitstream (synthesis + implementation)."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    result = build_cmd(
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
        do_program=do_program,
    )

    raise SystemExit(result)


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
    """Lint/syntax check with Verilator or Icarus Verilog."""
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
            wall=True,
            no_color=ctx.obj.get("no_color", False),
        )
    )


# --- Include path commands ---


@cli.group("include")
def include():
    """Manage include directories for the project."""
    pass


@include.command("ls")
@click.pass_context
def include_ls(ctx):
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
