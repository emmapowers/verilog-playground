# vproj daemon server - runs inside Vivado Tcl mode
# Usage: vivado -mode tcl -source server.tcl -tclargs <proj_dir>
# Or for GUI: source this file after setting ::vproj_proj_dir

package require Tcl 8.5

# Get project directory from args or variable
if {[info exists ::vproj_proj_dir]} {
    set proj_dir $::vproj_proj_dir
} elseif {$argc >= 1} {
    set proj_dir [lindex $argv 0]
} else {
    set proj_dir [pwd]
}

# Port file location (project-local)
set port_file [file join $proj_dir ".vproj-port"]

# Find an available port
set port 8230
while {1} {
    if {![catch {socket -server accept_connection $port} server_sock]} {
        break
    }
    incr port
    if {$port > 8300} {
        puts stderr "ERROR: No available port in range 8230-8300"
        exit 1
    }
}

# Write port file
set f [open $port_file w]
puts $f $port
close $f

# Store for cleanup
set ::vproj_port_file $port_file

proc log {msg} {
    puts stderr "\[vproj-daemon\] $msg"
    flush stderr
}

proc accept_connection {client addr clientport} {
    log "Client connected from $addr:$clientport"
    fconfigure $client -buffering line -blocking 1
    fileevent $client readable [list handle_client $client]
}

proc handle_client {client} {
    if {[eof $client]} {
        log "Client disconnected"
        close $client
        return
    }

    # Read all available lines until empty line (end of command)
    set cmd_lines {}
    while {1} {
        if {[gets $client line] < 0} {
            # EOF or error
            break
        }
        if {$line eq "END_CMD"} {
            break
        }
        lappend cmd_lines $line
    }

    if {[llength $cmd_lines] == 0} {
        return
    }

    set cmd [join $cmd_lines "\n"]
    log "Executing: [string range $cmd 0 80]..."

    # Special command: QUIT
    if {$cmd eq "QUIT"} {
        puts $client "OK"
        puts $client "Shutting down"
        puts $client "END_RESPONSE"
        flush $client
        close $client
        log "Shutdown requested"
        # Clean up port file
        file delete -force $::vproj_port_file
        exit 0
    }

    # Special command: PING
    if {$cmd eq "PING"} {
        puts $client "OK"
        puts $client "PONG"
        puts $client "END_RESPONSE"
        flush $client
        return
    }

    # Execute the TCL command
    if {[catch {uplevel #0 $cmd} result]} {
        puts $client "ERROR"
        foreach line [split $result "\n"] {
            puts $client $line
        }
    } else {
        puts $client "OK"
        if {$result ne ""} {
            foreach line [split $result "\n"] {
                puts $client $line
            }
        }
    }
    puts $client "END_RESPONSE"
    flush $client
}

# Flag to indicate server mode (commands should not close project)
set ::vproj_server_mode 1

# Start server
set pid [pid]
log "Starting vproj server on port $port (PID: $pid)"
log "Port file: $port_file"
# Note: server socket was already created in the port-finding loop above

# Enter event loop
vwait forever
