# Verilog Playground

A learning project for Verilog/SystemVerilog development targeting the Digilent Basys 3 (Artix-7 FPGA).

## Project Structure

```
fpga.srcs/
  sources_1/new/     # RTL source files (.sv)
  constrs_1/new/     # Constraint files (.xdc)
  sim_1/new/         # Testbench files
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

`vproj` is a CLI tool for managing Vivado projects without the GUI. It wraps Vivado's TCL interface to provide fast, scriptable commands.

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

### Server Mode

Start a persistent Vivado process to eliminate startup overhead (~15s per command → instant):

```bash
vproj server start   # Start server
vproj ls             # Instant
vproj server stop    # Stop when done
```

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
