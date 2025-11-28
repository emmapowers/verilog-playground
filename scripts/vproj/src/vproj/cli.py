"""Main CLI entry point for vproj."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from .cli_utils import vivado_command
from .constants import Fileset
from .context import VprojContext
from .vivado import PROJECT_DIR_DEFAULT, check_vivado_available
from .project import (
    list_cmd,
    add_files_cmd,
    add_src_cmd,
    add_xdc_cmd,
    add_sim_cmd,
    add_ip_cmd,
    remove_cmd,
    mv_cmd,
    get_top_module,
    set_top_module,
    get_hierarchy,
    info_cmd,
)
from .tcl_export import export_tcl_cmd
from .tcl_import import import_tcl_cmd
from .build import build_cmd
from .board import (
    board_info_cmd,
    board_install_cmd,
    board_uninstall_cmd,
    board_list_cmd,
    board_refresh_cmd,
    board_update_cmd,
    board_set_cmd,
    board_clear_cmd,
)
from .part import (
    part_info_cmd,
    part_set_cmd,
    part_list_cmd,
)
from .program import program_cmd
from .clean import clean_cmd
from .utils import display_path


# Command categories for help formatting
COMMAND_CATEGORIES = {
    "Project": ["info", "ls", "top", "tree", "add-src", "add-xdc", "add-sim", "add-ip", "rm", "mv", "include"],
    "Build": ["build", "program", "clean"],
    "Verify": ["check", "lint", "sim"],
    "Messages": ["msg", "log"],
    "TCL": ["export-tcl", "import-tcl"],
    "Board": ["board"],
    "Server": ["server"],
    "Hooks": ["hook"],
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


# --- Project info ---


@cli.command("info")
@click.pass_context
def info_(ctx):
    """Show project information and metadata."""
    from .daemon import find_server

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    info = info_cmd(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )

    if not info:
        click.echo("Failed to get project info", err=True)
        raise SystemExit(1)

    no_color = ctx.obj.get("no_color", False)

    def label(text: str) -> str:
        if no_color:
            return text
        return click.style(text, fg="cyan")

    def value(text: str, bold: bool = False) -> str:
        if no_color or not bold:
            return text
        return click.style(text, bold=True)

    # Project
    click.echo(f"{label('Project:')}      {value(info.get('project_name', ''), bold=True)}")
    click.echo(f"{label('XPR Path:')}     {display_path(info.get('xpr_path', ''))}")

    # Vivado
    click.echo(f"{label('Vivado:')}       {info.get('vivado_version', '')}")
    click.echo(f"{label('Vivado Path:')}  {display_path(info.get('vivado_path', ''))}")

    # Part & Board
    part = info.get("part", "")
    board = info.get("board_part", "")
    click.echo(f"{label('Part:')}         {part}")
    if board:
        click.echo(f"{label('Board:')}        {board}")

    # Top module
    top = info.get("top", "")
    click.echo(f"{label('Top Module:')}   {value(top, bold=True)}")

    # Files
    src = info.get("source_count", "0")
    xdc = info.get("constraint_count", "0")
    sim = info.get("sim_count", "0")
    click.echo(f"{label('Files:')}        {src} sources, {xdc} constraints, {sim} sim")

    # Include dirs
    inc_dirs = info.get("include_dirs", "")
    if inc_dirs:
        click.echo(f"{label('Include Dirs:')} {inc_dirs}")

    # Server status
    server_info = find_server(ctx.obj["proj_dir"])
    if server_info.running:
        mode = "GUI" if server_info.is_gui else "daemon"
        if no_color:
            click.echo(f"Server:        running ({mode}) on port {server_info.port}")
        else:
            click.echo(f"{label('Server:')}       {click.style('running', fg='green')} ({mode}) on port {server_info.port}")
    else:
        click.echo(f"{label('Server:')}       not running")


# --- File listing ---


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
            rel_path = display_path(path)
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
            rel_path = display_path(path)
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
@vivado_command()
def add_src(ctx: VprojContext, files):
    """Add HDL source files (.v, .sv, .vhd) to sources_1."""
    return add_files_cmd(files, Fileset.SOURCES, ctx)


@cli.command("add-xdc")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@vivado_command()
def add_xdc(ctx: VprojContext, files):
    """Add constraint files (.xdc) to constrs_1."""
    return add_files_cmd(files, Fileset.CONSTRAINTS, ctx)


@cli.command("add-sim")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@vivado_command()
def add_sim(ctx: VprojContext, files):
    """Add testbench files to sim_1."""
    return add_files_cmd(files, Fileset.SIMULATION, ctx)


@cli.command("add-ip")
@click.argument("files", type=click.Path(path_type=Path, exists=True), nargs=-1, required=True)
@vivado_command()
def add_ip(ctx: VprojContext, files):
    """Add IP files (.xci, .bd) to sources_1."""
    return add_files_cmd(files, Fileset.SOURCES, ctx)


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
@click.argument("sources", type=click.Path(path_type=Path), nargs=-1, required=True)
@click.argument("dest", type=click.Path(path_type=Path))
@click.option("-r", "--recursive", is_flag=True, help="Move folder contents recursively.")
@click.pass_context
def mv_(ctx, sources, dest, recursive):
    """Move/rename files or folders (disk + project).

    With multiple sources, DEST must be a directory.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        mv_cmd(
            sources,
            dest,
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
@click.option(
    "--no-board-install",
    is_flag=True,
    help="Skip automatic board file installation from xhub.",
)
@click.pass_context
def import_tcl(ctx, project_tcl, workdir, force, wipe, no_board_install):
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
            install_board=not no_board_install,
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
@click.option("-t", "--timeout", "timeout", type=str, default=None,
              help="Max simulation time (e.g., '1ms', '10us'). Without this, runs until $finish.")
@click.option("--open", "open_waveform", is_flag=True, help="Open waveform in gtkwave after simulation.")
@click.option("-I", "--include", "include_dirs", multiple=True,
              type=click.Path(path_type=Path, exists=True),
              help="Add include directory (can specify multiple times).")
@click.pass_context
def sim(ctx, testbench, use_xsim, use_iverilog, use_verilator, use_fst, output, timeout, open_waveform, include_dirs):
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
            timeout,
            open_waveform,
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

    no_color = ctx.obj.get("no_color", False)

    dirs = include_list_cmd(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
        return_data=True,
    )

    if isinstance(dirs, int):
        raise SystemExit(dirs)

    if not dirs:
        click.echo("No include directories configured")
        raise SystemExit(0)

    if no_color:
        for d in dirs:
            click.echo(display_path(d))
    else:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_header=True)
        table.add_column("Include Directory")

        for d in dirs:
            table.add_row(display_path(d))

        console.print(table)

    raise SystemExit(0)


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


# --- Board commands ---


@cli.group("board")
def board():
    """Manage board files for the project."""
    pass


@board.command("info")
@click.pass_context
def board_info(ctx):
    """Show current board configuration."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        board_info_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@board.command("install")
@click.argument("pattern", required=False)
@click.pass_context
def board_install(ctx, pattern):
    """Install board files from xhub store.

    If PATTERN is provided, installs boards matching that pattern.
    Otherwise, installs board files for the current project's board.
    """
    from .daemon import restart_daemon

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    result = board_install_cmd(
        pattern,
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )
    if result == 0:
        restart_daemon(ctx.obj["proj_dir"], ctx.obj["settings"], ctx.obj["quiet"])
    raise SystemExit(result)


@board.command("list")
@click.argument("pattern", required=False)
@click.pass_context
def board_list(ctx, pattern):
    """List available boards in xhub store.

    If PATTERN is provided, filters boards matching that pattern.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        board_list_cmd(
            pattern,
            ctx.obj["settings"],
            ctx.obj["proj_dir"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@board.command("uninstall")
@click.argument("pattern")
@click.pass_context
def board_uninstall(ctx, pattern):
    """Uninstall board files from xhub store.

    PATTERN specifies which boards to uninstall (e.g., 'nexys-a7-100t').
    """
    from .daemon import restart_daemon

    # Always check with batch=True because xhub::uninstall only works in batch mode
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], batch=True)
    result = board_uninstall_cmd(
        pattern,
        ctx.obj["settings"],
        ctx.obj["proj_dir"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )
    if result == 0:
        restart_daemon(ctx.obj["proj_dir"], ctx.obj["settings"], ctx.obj["quiet"])
    raise SystemExit(result)


@board.command("refresh")
@click.pass_context
def board_refresh(ctx):
    """Refresh board catalog from GitHub.

    Fetches the latest board file list from Xilinx's board store.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        board_refresh_cmd(
            ctx.obj["settings"],
            ctx.obj["proj_dir"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@board.command("update")
@click.argument("pattern", required=False)
@click.pass_context
def board_update(ctx, pattern):
    """Update installed board files to latest versions.

    If PATTERN is provided, updates only boards matching that pattern.
    Otherwise, updates all installed boards.
    """
    from .daemon import restart_daemon

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    result = board_update_cmd(
        pattern,
        ctx.obj["settings"],
        ctx.obj["proj_dir"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )
    if result == 0:
        restart_daemon(ctx.obj["proj_dir"], ctx.obj["settings"], ctx.obj["quiet"])
    raise SystemExit(result)


@board.command("set")
@click.argument("board_part")
@click.pass_context
def board_set(ctx, board_part):
    """Set the board for this project.

    BOARD_PART is the full board identifier (e.g., 'digilentinc.com:nexys-a7-100t:part0:1.3').

    Setting a board also sets the FPGA part automatically.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        board_set_cmd(
            board_part,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@board.command("clear")
@click.pass_context
def board_clear(ctx):
    """Clear the board from this project.

    The FPGA part is retained.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        board_clear_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


# --- Part commands ---


@cli.group("part", invoke_without_command=True)
@click.pass_context
def part(ctx):
    """Manage the FPGA part for the project.

    Use 'vproj part' to show current FPGA part.
    Use 'vproj board' to manage board files instead.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(part_info)


@part.command("info")
@click.pass_context
def part_info(ctx):
    """Show current FPGA part configuration."""
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        part_info_cmd(
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@part.command("set")
@click.argument("part_name")
@click.pass_context
def part_set(ctx, part_name):
    """Set the FPGA part directly.

    PART_NAME is the FPGA part identifier (e.g., 'xc7a100tcsg324-1').

    Note: This clears any board_part setting. Use 'vproj board set' instead
    if you want board-specific pin assignments and IP.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        part_set_cmd(
            part_name,
            ctx.obj["proj_hint"],
            ctx.obj["proj_dir"],
            ctx.obj["settings"],
            ctx.obj["quiet"],
            batch=ctx.obj["batch"],
            gui=ctx.obj["gui"],
            daemon=ctx.obj["daemon"],
        )
    )


@part.command("list")
@click.argument("pattern", required=False)
@click.pass_context
def part_list(ctx, pattern):
    """List available FPGA parts.

    If PATTERN is provided, filters parts matching that pattern.
    """
    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])
    raise SystemExit(
        part_list_cmd(
            pattern,
            ctx.obj["settings"],
            ctx.obj["proj_dir"],
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


# --- Log commands ---


@cli.group("log", invoke_without_command=True)
@click.option("-n", "--tail", type=int, help="Show last N lines.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.pass_context
def log(ctx, tail, grep_pattern):
    """View full build logs.

    Without subcommand, shows last 50 lines of synthesis log.
    Use 'vproj msg' to view just warnings/errors/critical messages.
    """
    if ctx.invoked_subcommand is None:
        # Default: show synthesis log
        _show_full_log(ctx, "synth", tail or 50, grep_pattern)


def _show_full_log(ctx, log_type_str, tail, grep_pattern):
    """Show full log content."""
    from .logs import LogType, get_log_path, read_log_lines

    log_type = LogType(log_type_str)
    log_path = get_log_path(log_type, ctx.obj["proj_dir"])

    if not log_path:
        click.echo(f"{log_type_str.capitalize()} log not found. Run 'vproj build' first.", err=True)
        raise SystemExit(1)

    lines = read_log_lines(log_path, tail=tail, grep_pattern=grep_pattern)

    for line in lines:
        click.echo(line)

    raise SystemExit(0)


@log.command("synth")
@click.option("-n", "--tail", type=int, default=50, show_default=True, help="Show last N lines.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.option("--all", "show_all", is_flag=True, help="Show full log.")
@click.pass_context
def log_synth(ctx, tail, grep_pattern, show_all):
    """View synthesis log."""
    _show_full_log(ctx, "synth", None if show_all else tail, grep_pattern)


@log.command("impl")
@click.option("-n", "--tail", type=int, default=50, show_default=True, help="Show last N lines.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.option("--all", "show_all", is_flag=True, help="Show full log.")
@click.pass_context
def log_impl(ctx, tail, grep_pattern, show_all):
    """View implementation log."""
    _show_full_log(ctx, "impl", None if show_all else tail, grep_pattern)


@log.command("daemon")
@click.option("-n", "--tail", type=int, default=50, show_default=True, help="Show last N lines.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.option("--all", "show_all", is_flag=True, help="Show full log.")
@click.pass_context
def log_daemon(ctx, tail, grep_pattern, show_all):
    """View daemon log."""
    from .logs import LogType, get_log_path, read_log_lines

    log_path = get_log_path(LogType.DAEMON)
    if not log_path:
        click.echo("Daemon log not found.", err=True)
        raise SystemExit(1)

    lines = read_log_lines(log_path, tail=None if show_all else tail, grep_pattern=grep_pattern)

    for line in lines:
        click.echo(line)

    raise SystemExit(0)


@log.command("sim")
@click.option("-n", "--tail", type=int, default=50, show_default=True, help="Show last N lines.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.option("--all", "show_all", is_flag=True, help="Show full log.")
@click.pass_context
def log_sim(ctx, tail, grep_pattern, show_all):
    """View simulation log."""
    _show_full_log(ctx, "sim", None if show_all else tail, grep_pattern)


# --- Message commands ---


@cli.group("msg", invoke_without_command=True)
@click.option("-w", "--warnings", "show_warnings", is_flag=True, help="Show warnings only.")
@click.option("-e", "--errors", "show_errors", is_flag=True, help="Show errors only.")
@click.option("-c", "--critical", "show_critical", is_flag=True, help="Show critical warnings only.")
@click.option("--grep", "grep_pattern", help="Filter by regex pattern.")
@click.option("--synth", "synth_only", is_flag=True, help="Show synthesis messages only.")
@click.option("--impl", "impl_only", is_flag=True, help="Show implementation messages only.")
@click.pass_context
def msg(ctx, show_warnings, show_errors, show_critical, grep_pattern, synth_only, impl_only):
    """View build messages (warnings/errors/critical).

    Without subcommand, shows messages from the last build.
    Use 'msg info' for Vivado message configuration.
    Use 'msg reset' to clear message suppressions.
    """
    if ctx.invoked_subcommand is None:
        _show_messages(ctx, show_warnings, show_errors, show_critical, grep_pattern, synth_only, impl_only)


def _show_messages(ctx, show_warnings, show_errors, show_critical, grep_pattern, synth_only, impl_only):
    """Show messages from build logs."""
    from rich.console import Console

    from .logs import LogType, Severity, extract_messages, format_messages, get_log_path

    no_color = ctx.obj.get("no_color", False)
    console = Console()

    # Determine which logs to show
    logs_to_show = []
    if synth_only:
        logs_to_show = [(LogType.SYNTH, "Synthesis")]
    elif impl_only:
        logs_to_show = [(LogType.IMPL, "Implementation")]
    else:
        logs_to_show = [(LogType.SYNTH, "Synthesis"), (LogType.IMPL, "Implementation")]

    # Collect messages
    all_messages = []

    for log_type, label in logs_to_show:
        log_path = get_log_path(log_type, ctx.obj["proj_dir"])
        if not log_path:
            continue

        # Filter by severity
        severities = None
        if show_warnings or show_errors or show_critical:
            severities = set()
            if show_warnings:
                severities.add(Severity.WARNING)
            if show_errors:
                severities.add(Severity.ERROR)
            if show_critical:
                severities.add(Severity.CRITICAL)

        messages = extract_messages(log_path, severities=severities, grep_pattern=grep_pattern)
        if messages:
            all_messages.append((label, messages))

    if not all_messages:
        click.echo("No messages found.", err=True)
        raise SystemExit(0)

    for label, messages in all_messages:
        if not no_color:
            console.print(f"[bold cyan]{label}:[/bold cyan]")
        else:
            click.echo(f"{label}:")

        formatted = format_messages(messages, no_color=no_color)
        if no_color:
            for line in formatted:
                click.echo(f"  {line}")
        else:
            for line in formatted:
                console.print(f"  {line}")

    raise SystemExit(0)


@msg.command("info")
@click.pass_context
def msg_info(ctx):
    """Show Vivado message configuration and suppression state."""
    from rich.console import Console

    from .messages import get_message_config

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    config = get_message_config(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )

    if not config:
        click.echo("Failed to get message configuration", err=True)
        raise SystemExit(1)

    no_color = ctx.obj.get("no_color", False)

    def status(suppressed: bool) -> str:
        if no_color:
            return "suppressed" if suppressed else "normal"
        return "[yellow]suppressed[/yellow]" if suppressed else "[green]normal[/green]"

    if no_color:
        click.echo("Message Configuration:")
        click.echo(f"  INFO:     {status(config.info_suppressed)}")
        click.echo(f"  WARNING:  {status(config.warning_suppressed)}")
        click.echo(f"  ERROR:    {status(config.error_suppressed)}")
        click.echo(f"  CRITICAL: {status(config.critical_suppressed)}")
        click.echo("")
        click.echo("Counts (current session):")
        click.echo(f"  Info:     {config.info_count}")
        click.echo(f"  Warnings: {config.warning_count}")
        click.echo(f"  Errors:   {config.error_count}")
        click.echo(f"  Critical: {config.critical_count}")
    else:
        console = Console()
        console.print("Message Configuration:")
        console.print(f"  INFO:     {status(config.info_suppressed)}")
        console.print(f"  WARNING:  {status(config.warning_suppressed)}")
        console.print(f"  ERROR:    {status(config.error_suppressed)}")
        console.print(f"  CRITICAL: {status(config.critical_suppressed)}")
        console.print("")
        console.print("Counts (current session):")
        console.print(f"  Info:     {config.info_count}")
        console.print(f"  Warnings: [dim]{config.warning_count}[/dim]")
        console.print(f"  Errors:   [red]{config.error_count}[/red]" if config.error_count else f"  Errors:   {config.error_count}")
        console.print(f"  Critical: [yellow]{config.critical_count}[/yellow]" if config.critical_count else f"  Critical: {config.critical_count}")

    raise SystemExit(0)


@msg.command("reset")
@click.pass_context
def msg_reset(ctx):
    """Reset all message suppressions."""
    from .messages import reset_message_config

    check_vivado_available(ctx.obj["settings"], ctx.obj["proj_dir"], ctx.obj["batch"])

    result = reset_message_config(
        ctx.obj["proj_hint"],
        ctx.obj["proj_dir"],
        ctx.obj["settings"],
        ctx.obj["quiet"],
        batch=ctx.obj["batch"],
        gui=ctx.obj["gui"],
        daemon=ctx.obj["daemon"],
    )

    if result == 0:
        click.echo("Message suppressions reset")
    else:
        click.echo("Failed to reset message suppressions", err=True)

    raise SystemExit(result)


# --- Hook commands ---


@cli.group("hook")
def hook():
    """Manage git pre-commit hooks for auto-exporting project.tcl."""
    pass


@hook.command("install")
@click.argument("mode", type=click.Choice(["warn", "block", "update"]))
def hook_install(mode):
    """Install pre-commit hook for auto-exporting project.tcl.

    MODE specifies behavior when project.tcl changes:

    \b
    warn   - warn but allow commit
    block  - error and block commit
    update - auto-stage and continue
    """
    from .hooks import HookMode, find_git_root, install_hook

    git_root = find_git_root()
    if not git_root:
        click.echo("Not in a git repository", err=True)
        raise SystemExit(1)

    success, message = install_hook(git_root, HookMode(mode))
    click.echo(message)
    raise SystemExit(0 if success else 1)


@hook.command("uninstall")
def hook_uninstall():
    """Remove pre-commit hook."""
    from .hooks import find_git_root, uninstall_hook

    git_root = find_git_root()
    if not git_root:
        click.echo("Not in a git repository", err=True)
        raise SystemExit(1)

    success, message = uninstall_hook(git_root)
    click.echo(message)
    raise SystemExit(0 if success else 1)


@hook.command("status")
def hook_status():
    """Check if pre-commit hook is installed."""
    from .hooks import find_git_root, get_current_mode

    git_root = find_git_root()
    if not git_root:
        click.echo("Not in a git repository", err=True)
        raise SystemExit(1)

    mode = get_current_mode(git_root)
    if mode:
        click.echo(f"Pre-commit hook installed (mode={mode.value})")
        raise SystemExit(0)
    else:
        click.echo("Pre-commit hook is not installed")
        raise SystemExit(1)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
