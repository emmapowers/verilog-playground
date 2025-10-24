# Program the FPGA over JTAG via hw_server.
# Usage: vivado -mode batch -source program.tcl -tclargs <path/to/bit>
# Or run with no args to use the most recent bit in impl_1.

proc latest_bit_in_impl {} {
  set impl_dir [file normalize [get_property DIRECTORY [get_runs impl_1]]]
  set bits [lsort -decreasing -command {string compare} [glob -nocomplain -types f "$impl_dir/*.bit"]]
  if {[llength $bits] == 0} { return "" }
  return [lindex $bits 0]
}

# Open project just to locate runs if needed
set proj [lindex [glob -nocomplain *.xpr] 0]
if {$proj ne ""} { open_project $proj }

# Resolve bitstream path
set bitfile ""
set argv_len [llength $argv]
if {$argv_len >= 1} {
  set bitfile [file normalize [lindex $argv 0]]
} else {
  set bitfile [latest_bit_in_impl]
}

if {$bitfile eq "" || ![file exists $bitfile]} {
  puts "ERROR: Bitstream not found. Pass it as an argument or build first."
  exit 3
}
puts "Using bitstream: $bitfile"

# Start or connect to hw_server (if separate daemon not already running)
# Typically hw_server is auto-launched on demand; this also works if one is already running.
open_hw
connect_hw_server -allow_non_jtag
open_hw_target

# Pick the first device by default
set devs [get_hw_devices]
if {[llength $devs] == 0} {
  puts "ERROR: No JTAG devices visible. Check cable/permissions."
  exit 4
}
current_hw_device [lindex $devs 0]

# Program
set_property PROGRAM.FILE $bitfile [current_hw_device]
program_hw_devices [current_hw_device]
refresh_hw_device [current_hw_device]

puts "DONE: Device programmed."
exit 0