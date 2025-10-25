# program.tcl — program FPGA over JTAG
# Usage:
#   vivado -mode batch -source program.tcl -tclargs path/to/top.bit
# or (no args):
#   vivado -mode batch -source program.tcl

proc _project_xpr {} {
  set xs [glob -nocomplain -types f project_files/*.xpr]
  if {[llength $xs]} { return [lindex $xs 0] }
  return ""
}

proc _bit_from_runs {} {
  # Requires an open project; prefer run property over directory glob
  if {![llength [get_projects -quiet]]} { return "" }
  set r [get_runs -quiet impl_1]
  if {![llength $r]} { return "" }
  set bf [get_property BITSTREAM.FILE $r]
  if {$bf ne "" && [file exists $bf]} { return $bf }

  # Fallback: look in the impl_1 run directory
  set d [get_property DIRECTORY $r]
  set bits [lsort -decreasing [glob -nocomplain -types f [file join $d *.bit]]]
  if {[llength $bits]} { return [lindex $bits 0] }
  return ""
}

proc _bit_from_tree {} {
  # Last-resort: any .bit under project_files/
  set bits [lsort -decreasing [glob -nocomplain -types f -tails -directory project_files -recursive *.bit]]
  if {[llength $bits]} { return [file normalize [file join project_files [lindex $bits 0]]] }
  return ""
}

# Resolve bitfile
set bitfile ""
if {[llength $argv] >= 1} {
  set bitfile [file normalize [lindex $argv 0]]
} else {
  # Try with the project open (if present)
  set xpr [_project_xpr]
  if {$xpr ne ""} {
    open_project $xpr
    set bitfile [_bit_from_runs]
    close_project
  }
  if {$bitfile eq ""} {
    set bitfile [_bit_from_tree]
  }
}

if {$bitfile eq "" || ![file exists $bitfile]} {
  puts "ERROR: Bitstream not found. Pass one via -tclargs or build first."
  exit 3
}
puts "Using bitstream: $bitfile"

# --- Hardware programming ---
open_hw
# If a separate daemon is already running this just connects.
catch { connect_hw_server -allow_non_jtag } ;# ignore if already connected
# Some cables need a moment to enumerate
set tries 10
while {$tries > 0} {
  set ok [catch { open_hw_target } msg]
  if {!$ok} { break }
  after 300
  incr tries -1
}
if {[catch { get_hw_devices } devs] || [llength $devs] == 0} {
  puts "ERROR: No JTAG devices visible. Check cable/permissions."
  exit 4
}
current_hw_device [lindex $devs 0]
refresh_hw_device [current_hw_device]

set_property PROGRAM.FILE $bitfile [current_hw_device]
program_hw_devices [current_hw_device]
refresh_hw_device  [current_hw_device]

puts "DONE: Device programmed."
exit 0