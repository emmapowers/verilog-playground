# build.tcl — synth + impl + reports + bit
set proj_dir  [file normalize "project_files"]
set xprs [glob -nocomplain -types f -directory $proj_dir *.xpr]
if {[llength $xprs] == 0} { error "No .xpr found in $proj_dir" }
open_project [lindex $xprs 0]

# Optional: set top if needed
# set_property top top [current_fileset]

update_compile_order -fileset sources_1

catch { reset_run synth_1 }
catch { reset_run impl_1 }

launch_runs synth_1 -jobs 8
wait_on_run synth_1

launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1

open_run impl_1

# Reports directory
set rptdir [file normalize "$proj_dir/reports"]
file mkdir $rptdir

# Reports (no -pb)
report_utilization    -file "$rptdir/utilization.rpt"
report_timing_summary -file "$rptdir/timing_summary.rpt" -warn_on_violation

set bitfile [get_property BITSTREAM.FILE [get_runs impl_1]]
puts "BITSTREAM: $bitfile"

close_project