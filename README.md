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
- **Messages & Logs**: View build warnings/errors with filtering
- **Board management**: Auto-install board files from Vivado xhub store
- **Server mode**: Persistent Vivado process for instant command execution

### Commands

| Command | Description |
|---------|-------------|
| `vproj info` | Show project info (part, board, top, Vivado version) |
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
| `vproj msg` | Show build messages (warnings/errors) |
| `vproj log` | View build logs |
| `vproj import-tcl <file>` | Import project from TCL |
| `vproj export-tcl` | Export project to TCL |
| `vproj board info` | Show board configuration |
| `vproj board install` | Install board files from xhub |
| `vproj board uninstall <pattern>` | Uninstall board files |
| `vproj board refresh` | Refresh board catalog from GitHub |
| `vproj board update [pattern]` | Update installed boards |
| `vproj board list [pattern]` | List available boards |

### TCL Import/Export

Keep Vivado project files out of git by using TCL scripts:

```bash
# After cloning - recreate project from TCL
vproj import-tcl project.tcl

# Before committing - export changes to TCL
vproj export-tcl
```

Board files are automatically installed from Vivado's xhub store during import if missing. Use `--no-board-install` to skip.

### Server Mode

Start a persistent Vivado process to eliminate startup overhead (~15s per command → instant):

```bash
vproj server start   # Start server
vproj ls             # Instant
vproj server stop    # Stop when done
```

### Messages and Logs

View build messages (warnings/errors/critical) with filtering:

```bash
vproj msg              # Show all messages from last build
vproj msg -w           # Warnings only
vproj msg -e           # Errors only
vproj msg -c           # Critical warnings only
vproj msg --grep PAT   # Filter by pattern
vproj msg --synth      # Synthesis only
vproj msg info         # Show Vivado message suppression state
vproj msg reset        # Reset message suppressions
```

View full build logs:

```bash
vproj log              # Last 50 lines of synthesis log
vproj log synth        # Synthesis log
vproj log impl         # Implementation log
vproj log daemon       # vproj daemon log
vproj log --all        # Full log
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
