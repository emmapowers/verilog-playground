# Claude Instructions

## Important Rules

- This is a project to help me learn verilog. **Never generate verilog code.** You may provide verilog code examples if requested, but only for syntax/language features.
- Generating code for tooling (Python, TCL, etc.) is OK.
- User-facing documentation is in README.md. This file is for Claude-specific instructions.

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

## vproj Reference

vproj is a CLI tool for managing Vivado projects from the terminal. Requires Vivado 2025.1.

```bash
# If Vivado not in PATH:
vproj --settings ~/xilinx/2025.1/Vivado/settings64.sh <command>
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
- `vproj check` - Lint/syntax check with Verilator

### Simulation
- `vproj sim <testbench>` - Run simulation with xsim
- `vproj sim <testbench> -t <time>` - Limit simulation time (e.g., `1ms`, `10us`)
- `vproj sim <testbench> --open` - Open waveform in gtkwave after
- `vproj sim <testbench> --iverilog` - Use Icarus Verilog instead
- `vproj sim <testbench> --verilator` - Use Verilator instead

### TCL Import/Export
- `vproj export-tcl` - Export project to `project.tcl`
- `vproj import-tcl project.tcl` - Recreate Vivado project from TCL
- `vproj import-tcl --no-board-install project.tcl` - Import without auto-installing board files

### Board Management
- `vproj board` - Show current board configuration
- `vproj board set <board_part>` - Set board
- `vproj board clear` - Clear board (retain FPGA part)
- `vproj board install [pattern]` - Install board files from xhub
- `vproj board uninstall <pattern>` - Uninstall board files
- `vproj board list [pattern]` - List available boards

### Part Management
- `vproj part` - Show current FPGA part
- `vproj part set <part>` - Set FPGA part directly
- `vproj part list [pattern]` - List available FPGA parts

### Server Mode
- `vproj server start` - Start Vivado server
- `vproj server stop` - Stop the server
- `vproj server status` - Check if server is running

### Messages and Logs
```bash
vproj msg                    # Show all messages from last build
vproj msg -w                 # Warnings only
vproj msg -e                 # Errors only
vproj msg --grep "timing"    # Filter by pattern
vproj log synth              # View synthesis log
vproj log impl               # View implementation log
```

## Testing

Uses cocotb + verilator + pytest. Requires pixi environment.

- `pixi run pytest` - Run all tests
- `pixi run pytest tests/test_bcd_encoder.py` - Run specific test

Tests use the `@coco_test` decorator from `tests/coco_helper.py`.

## vproj Development

- **Be VERY careful when modifying vproj to not break tcl import and export.** It's quite delicate.
- vproj is a Python package at `scripts/vproj/` installed in editable mode via pixi.
- Use `display_path()` from `vproj.utils` when displaying paths to users.
- New code patterns to follow:
  - Use `VprojContext` from `vproj.context` instead of passing 8 individual parameters
  - Use `Fileset` and `RunName` enums from `vproj.constants` instead of magic strings
  - Use `@vivado_command()` decorator from `vproj.cli_utils` for CLI commands
  - Use `add_files_cmd()` with `Fileset` enum for adding files
- vproj is in the path, no need to pixi run... it