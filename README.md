# Verilog Playground

A learning project for Verilog/SystemVerilog development targeting the Digilent Nexys A7 (Artix-7 FPGA).

## Requirements

- Vivado 2025.1
- [pixi](https://pixi.sh) for Python environment management
- verilator (for linting and simulation)

## Quick Start

```bash
# Set up environment
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

`vproj` is a CLI tool for Verilog/FPGA development that lets you use your favorite editor and terminal while maintaining Vivado project files and build infrastructure.

![vproj build --program](docs/vproj-build-and-program.png)

### Features

- **Project management** - Add/remove source files, constraints, and testbenches
- **Build pipeline** - Synthesis, implementation, and bitstream generation with live progress
- **Device programming** - Program FPGA over JTAG
- **Fast linting** - Syntax checking with Verilator (no Vivado startup)
- **Simulation** - Run testbenches with xsim, Icarus Verilog, or Verilator
- **TCL import/export** - Keep Vivado project files out of git
- **Server mode** - Persistent Vivado process for instant command execution
- **Board management** - Auto-install board files from Xilinx xhub store
- **Build messages** - View and filter synthesis/implementation warnings and errors

### Commands

#### Project Management

| Command | Description |
|---------|-------------|
| `vproj info` | Show project info (part, board, top module, Vivado version) |
| `vproj ls` | List project files (highlights top module) |
| `vproj top` | Print current top module |
| `vproj top <module>` | Set top module |
| `vproj tree` | Show module instantiation hierarchy |
| `vproj add-src <files>` | Add HDL source files to project |
| `vproj add-xdc <files>` | Add constraint files |
| `vproj add-sim <files>` | Add testbench files |
| `vproj rm <files>` | Remove files from project |
| `vproj mv <files...> <dest>` | Move/rename files (updates project references) |
| `vproj include ls` | List include directories |
| `vproj include add <dirs>` | Add include directories |
| `vproj include rm <dirs>` | Remove include directories |

#### Build & Program

| Command | Description |
|---------|-------------|
| `vproj build` | Build bitstream (synthesis + implementation) |
| `vproj build --program` | Build and program FPGA |
| `vproj build --synth-only` | Run synthesis only |
| `vproj build --force` | Force rebuild from scratch |
| `vproj program` | Program the FPGA with latest bitstream |
| `vproj clean` | Clean build artifacts |

#### Verification & Simulation

| Command | Description |
|---------|-------------|
| `vproj check` | Lint/syntax check with Verilator |
| `vproj sim <testbench>` | Run simulation with xsim |
| `vproj sim <tb> -t 1ms` | Run for specified time |
| `vproj sim <tb> --open` | Open waveform in GTKWave after |
| `vproj sim <tb> --iverilog` | Use Icarus Verilog instead of xsim |
| `vproj sim <tb> --verilator` | Use Verilator instead of xsim |

#### TCL Import/Export

| Command | Description |
|---------|-------------|
| `vproj import-tcl <file>` | Recreate Vivado project from TCL script |
| `vproj export-tcl` | Export project to `project.tcl` |

Keep Vivado project files out of git:

```bash
# After cloning - recreate project
vproj import-tcl project.tcl

# Before committing - export changes
vproj export-tcl
```

Board files are automatically installed during import if missing.

#### Board & Part Management

| Command | Description |
|---------|-------------|
| `vproj board` | Show current board configuration |
| `vproj board set <board>` | Set board (e.g., `digilentinc.com:nexys-a7-100t:part0:1.3`) |
| `vproj board clear` | Clear board (retain FPGA part) |
| `vproj board list [pattern]` | List available boards |
| `vproj board install [pattern]` | Install board files from xhub |
| `vproj board uninstall <pattern>` | Uninstall board files |
| `vproj part` | Show current FPGA part |
| `vproj part set <part>` | Set FPGA part directly |
| `vproj part list [pattern]` | List available FPGA parts |

#### Server Mode

Eliminate Vivado startup overhead (~15s per command → instant):

```bash
vproj server start    # Start persistent Vivado process
vproj ls              # Instant response
vproj server status   # Check if running
vproj server stop     # Stop when done
```

Commands automatically use the server if running, otherwise fall back to batch mode.

#### Git Hooks

Auto-export `project.tcl` before commits:

```bash
vproj hook install update   # Auto-stage project.tcl if changed
vproj hook install warn     # Warn if changed, allow commit
vproj hook install block    # Block commit if project.tcl changed
vproj hook status           # Check hook status
vproj hook uninstall        # Remove hook
```

#### Messages & Logs

| Command | Description |
|---------|-------------|
| `vproj msg` | Show all messages from last build |
| `vproj msg -w` | Warnings only |
| `vproj msg -e` | Errors only |
| `vproj msg -c` | Critical warnings only |
| `vproj msg --grep <pat>` | Filter by pattern |
| `vproj msg --synth` | Synthesis messages only |
| `vproj msg --impl` | Implementation messages only |
| `vproj log synth` | View synthesis log |
| `vproj log impl` | View implementation log |
| `vproj log --all` | View full log (not just last 50 lines) |

### Global Options

```bash
vproj --settings <path>   # Path to Vivado settings64.sh
vproj --no-color          # Disable colored output
vproj --quiet             # Suppress Vivado stdout
vproj --batch             # Force batch mode (no server)
vproj --gui               # Connect to Vivado GUI session
```

## Testing

Tests use cocotb + verilator + pytest:

```bash
pixi run pytest                         # Run all tests
pixi run pytest tests/test_module.py    # Run specific test
```

## License

MIT
