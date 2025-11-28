- This is a project to help me learn verilog. Never generate verilog code. You may provide verilog code examples if requested, but only for syntax/language features. Generating code for tooling is OK.
- User-facing documentation is in README.md. This file (CLAUDE.md) is for Claude-specific instructions.

## Project Structure

```
src/
  sources/           # RTL source files (.sv)
  constraints/       # Constraint files (.xdc)
  testbench/         # Testbench files
tests/               # Python/cocotb testbenches
scripts/vproj/       # vproj CLI tool
project.tcl          # Vivado project definition
```

## vproj

vproj is a CLI tool for Verilog/FPGA development that lets you use your favorite editor and terminal while maintaining Vivado project files and build infrastructure. It supports TCL import/export so you can keep generated Vivado project files out of git - just commit `project.tcl` and recreate the project on any machine.

![vproj build --program](docs/vproj-build-and-program.png)

## Build Commands

Requires Vivado 2025.1. Either source settings first or pass `--settings`.

```bash
# If Vivado not in PATH:
vproj --settings ~/xilinx/2025.1/Vivado/settings64.sh <command>

# Or source first, then run without --settings:
source ~/xilinx/2025.1/Vivado/settings64.sh
```

### Project Management
- `vproj info` - Show project info (part, board, top module, Vivado version, server status)
- `vproj ls` - List project files (highlights top module)
- `vproj top` - Print current top module
- `vproj top <module>` - Set top module
- `vproj tree` - Show module instantiation hierarchy
- `vproj add-src <files>` - Add source files to project
- `vproj add-xdc <files>` - Add constraint files
- `vproj add-sim <files>` - Add testbench files
- `vproj rm <files>` - Remove files from project

### Build
- `vproj build` - Build bitstream (synthesis + implementation)
- `vproj build --program` - Build and program FPGA
- `vproj program` - Program the board
- `vproj clean` - Clean build artifacts

### Verification
- `vproj check` - Lint/syntax check with Verilator (colorized output with summary)

### Simulation

Run simulations and generate VCD waveforms:

```bash
vproj sim src/testbench/tb_foo.sv              # Run until $finish (Ctrl+C to stop)
vproj sim src/testbench/tb_foo.sv -t 1ms       # Run for 1ms of simulation time
vproj sim src/testbench/tb_foo.sv --open       # Open waveform in gtkwave after
```

- `vproj sim <testbench>` - Run simulation with xsim (default), generates VCD
- `vproj sim <testbench> -t/--timeout <time>` - Limit simulation time (e.g., `1ms`, `10us`)
- `vproj sim <testbench> --open` - Open waveform in gtkwave after simulation
- `vproj sim <testbench> --iverilog` - Use Icarus Verilog instead of xsim
- `vproj sim <testbench> --verilator` - Use Verilator instead of xsim
- `vproj sim <testbench> -o <path>` - Custom output waveform path

Without `--timeout`, simulation runs until `$finish` or Ctrl+C. Progress is shown live. VCD is saved even if interrupted.

### TCL Import/Export

Keep Vivado project files out of git by using TCL scripts:

- `vproj export-tcl` - Export project to `project.tcl` (run before committing)
- `vproj import-tcl project.tcl` - Recreate Vivado project from TCL script
- `vproj import-tcl --no-board-install project.tcl` - Import without auto-installing board files

Workflow: After cloning, run `import-tcl` to create the project. Before committing changes, run `export-tcl` to update `project.tcl`.

Board files are auto-installed during import if missing. Use `--no-board-install` to skip.

### Board Management

Boards include the FPGA part + pin assignments + peripherals. Setting a board also sets the part.

- `vproj board` - Show current board configuration
- `vproj board set <board_part>` - Set board (e.g., `digilentinc.com:nexys-a7-100t:part0:1.3`)
- `vproj board clear` - Clear board (retain FPGA part)
- `vproj board install [pattern]` - Install board files from xhub
- `vproj board uninstall <pattern>` - Uninstall board files (requires Vivado in PATH or --settings)
- `vproj board list [pattern]` - List available boards
- `vproj board refresh` - Refresh board catalog
- `vproj board update [pattern]` - Update installed boards

### Part Management

Use `vproj part` for projects without a board, or to set the FPGA part directly.

- `vproj part` - Show current FPGA part
- `vproj part set <part>` - Set FPGA part directly (clears board_part)
- `vproj part list [pattern]` - List available FPGA parts

### Server Mode (Faster Commands)

Start a persistent Vivado process to eliminate startup overhead:

```bash
vproj server start    # Start server (takes ~15s, then stays running)
vproj ls              # ~instant (uses server)
vproj add-src foo.sv  # ~instant
vproj server stop     # Stop server when done
```

- `vproj server start` - Start Vivado server
- `vproj server stop` - Stop the server
- `vproj server status` - Check if server is running

Commands automatically use the server if running, otherwise fall back to batch mode.

### Messages and Logs

View build messages (warnings/errors/critical):

```bash
vproj msg                    # Show all messages from last build
vproj msg -w                 # Warnings only
vproj msg -e                 # Errors only
vproj msg -c                 # Critical warnings only
vproj msg --grep "timing"    # Filter by pattern
vproj msg --synth            # Synthesis messages only
vproj msg --impl             # Implementation messages only
```

- `vproj msg info` - Show Vivado message suppression state and counts
- `vproj msg reset` - Reset all message suppressions

View full build logs:

```bash
vproj log                    # Last 50 lines of synthesis log
vproj log synth              # Synthesis log
vproj log impl               # Implementation log
vproj log daemon             # vproj daemon log
vproj log sim                # Simulation log
vproj log synth --all        # Full log
vproj log synth --grep "error"  # Filter by pattern
```

### GUI Mode

Use `--gui` to connect to an existing Vivado GUI session that has the server running. This lets you use CLI commands while also having the GUI open for visualization and debugging.

## Testing

Uses cocotb + verilator + pytest. Requires pixi environment.

- `pixi run pytest` - Run all tests
- `pixi run pytest tests/test_bcd_encoder.py` - Run specific test file

Tests live in `tests/` and use the `@coco_test` decorator from `tests/coco_helper.py` to run cocotb simulations via verilator.

## vproj Development

- Be VERY careful when modifying vproj to not break tcl import and export. It's quite delicate.
- vproj is a Python package at `scripts/vproj/` installed in editable mode via pixi.
- Use `display_path()` from `vproj.utils` when displaying paths to users. It shows relative paths when under cwd, absolute otherwise.
