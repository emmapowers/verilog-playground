# Rebuild a *project-mode* Vivado design end-to-end (synth → impl → bit)
# Usage: vivado -mode batch -source build.tcl -nolog -nojournal -notrace

# Open the existing project
set proj [lindex [glob -nocomplain *.xpr] 0]
if {$proj eq ""} {
  puts "ERROR: No .xpr found in current directory."
  exit 1
}
open_project $proj

# Optional: pick a specific part/board constraint changes here if needed

# Clean and re-launch runs
reset_run synth_1
launch_runs synth_1 -jobs [expr {[get_param general.maxThreads] > 0 ? [get_param general.maxThreads] : 4}]
wait_on_run synth_1

reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs [expr {[get_param general.maxThreads] > 0 ? [get_param general.maxThreads] : 4}]
wait_on_run impl_1

# Report and paths
set impl_dir [get_property DIRECTORY [get_runs impl_1]]
set bitfile [file normalize "$impl_dir/top.bit"]
if {![file exists $bitfile]} {
  # Fallback: find any .bit produced in impl_1
  set bits [glob -nocomplain -types f "$impl_dir/*.bit"]
  if {[llength $bits] == 0} {
    puts "ERROR: No .bit file found."
    exit 2
  }
  set bitfile [lindex $bits 0]
}
puts "BITSTREAM: $bitfile"

# Optional useful reports
report_timing_summary    -file timing_summary.rpt
report_utilization       -file utilization.rpt

exit 0