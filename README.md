# Verilog Playground

A learning project for Verilog/SystemVerilog development targeting the Digilent Basys 3 (Artix-7 FPGA).

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

## Requirements

- Vivado 2025.1
- [pixi](https://pixi.sh) for Python environment management
- verilator (for linting and simulation)

## Quick Start

```bash
# Install dependencies and enter shell
pixi install
pixi shell

# Import Vivado project from TCL
vproj import-tcl project.tcl

# List project files
vproj ls

# Lint/syntax check
vproj check

# Build bitstream
vproj build

# Program FPGA
vproj program
```

## vproj

`vproj` is a CLI tool for Verilog/FPGA development that lets you use your favorite editor and terminal while maintaining Vivado project files and build infrastructure. It supports TCL import/export so you can keep generated Vivado project files out of git - just commit `project.tcl` and recreate the project on any machine.

![vproj build --program](docs/vproj-build-and-program.png)

### Features

- **Project management**: Add/remove source files, constraints, and testbenches
- **Build**: Synthesis, implementation, and bitstream generation with progress display
- **Programming**: Program FPGA over JTAG
- **Linting**: Fast syntax checking with Verilator
- **Server mode**: Persistent Vivado process for instant command execution

### Commands

| Command | Description |
|---------|-------------|
| `vproj ls` | List project files |
| `vproj add-src <files>` | Add source files |
| `vproj add-xdc <files>` | Add constraint files |
| `vproj add-sim <files>` | Add testbench files |
| `vproj rm <files>` | Remove files from project |
| `vproj top [module]` | Get/set top module |
| `vproj tree` | Show module hierarchy |
| `vproj check` | Lint with Verilator |
| `vproj build` | Build bitstream |
| `vproj build --program` | Build and program |
| `vproj program` | Program FPGA |
| `vproj import-tcl <file>` | Import project from TCL |
| `vproj export-tcl` | Export project to TCL |

### TCL Import/Export

Keep Vivado project files out of git by using TCL scripts:

```bash
# After cloning - recreate project from TCL
vproj import-tcl project.tcl

# Before committing - export changes to TCL
vproj export-tcl
```

### Server Mode

Start a persistent Vivado process to eliminate startup overhead (~15s per command → instant):

```bash
vproj server start   # Start server
vproj ls             # Instant
vproj server stop    # Stop when done
```

### GUI Mode

Use `--gui` to connect to an existing Vivado GUI session that has the server running. This lets you use CLI commands while also having the GUI open for visualization and debugging.

### Vivado Settings

If Vivado isn't in your PATH, pass the settings file:

```bash
vproj --settings ~/xilinx/2025.1/Vivado/settings64.sh build
```

## Testing

Tests use cocotb + verilator + pytest:

```bash
pytest                          # Run all tests
pytest tests/test_module.py     # Run specific test
```

## License

MIT
