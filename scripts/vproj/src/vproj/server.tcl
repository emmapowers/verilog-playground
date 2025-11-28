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

# Store proj_dir globally for interrupt checking
set ::vproj_proj_dir $proj_dir

# Check if interrupt flag is set (file-based signal from Python)
proc vproj_check_interrupt {} {
    set flag_file [file join $::vproj_proj_dir ".vproj-interrupt"]
    if {[file exists $flag_file]} {
        file delete -force $flag_file
        error "Interrupted by user"
    }
}

# Add xhub board store to board.repoPaths if it exists
# This ensures installed boards from xhub are visible
catch {
    set xhub_base "$::env(HOME)/.Xilinx/Vivado"
    foreach ver [glob -nocomplain -directory $xhub_base -type d *] {
        set boards_dir [file join $ver xhub board_store xilinx_board_store XilinxBoardStore Vivado [file tail $ver] boards]
        if {[file exists $boards_dir]} {
            set current_paths [get_param board.repoPaths]
            if {$current_paths eq ""} {
                set_param board.repoPaths $boards_dir
            } elseif {[string first $boards_dir $current_paths] == -1} {
                set_param board.repoPaths "$current_paths:$boards_dir"
            }
        }
    }
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

    # Execute the TCL command with streaming output
    # Override puts to send output immediately to client
    set ::_vproj_client $client

    # Save original puts and create streaming version
    rename puts _vproj_orig_puts
    proc puts {args} {
        # Parse puts arguments: puts ?-nonewline? ?channelId? string
        set nonewline 0
        set channel stdout
        set str ""

        if {[llength $args] == 1} {
            set str [lindex $args 0]
        } elseif {[llength $args] == 2} {
            if {[lindex $args 0] eq "-nonewline"} {
                set nonewline 1
                set str [lindex $args 1]
            } else {
                set channel [lindex $args 0]
                set str [lindex $args 1]
            }
        } elseif {[llength $args] == 3} {
            set nonewline 1
            set channel [lindex $args 1]
            set str [lindex $args 2]
        }

        # Stream stdout to client immediately, pass through others
        if {$channel eq "stdout"} {
            _vproj_orig_puts $::_vproj_client "OUTPUT:$str"
            flush $::_vproj_client
        } else {
            if {$nonewline} {
                _vproj_orig_puts -nonewline $channel $str
            } else {
                _vproj_orig_puts $channel $str
            }
        }
    }

    set error_occurred [catch {uplevel #0 $cmd} result]

    # Restore original puts
    rename puts {}
    rename _vproj_orig_puts puts

    if {$error_occurred} {
        puts $client "ERROR"
        foreach line [split $result "\n"] {
            puts $client $line
        }
    } else {
        puts $client "OK"
        # Send return value if any
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
