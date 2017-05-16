#!/usr/bin/tclsh
# The destructor of a class should be virtual

proc createMachine {initState} {
    set machine [dict create state $initState bracesCounter 0]
    return $machine
}

foreach fileName [getSourceFileNames] {
    set machines [list]
    
    set prev1 ""
    set prev2 ""
    foreach token [getTokens $fileName 1 0 -1 -1 {class struct leftbrace rightbrace virtual compl identifier semicolon}] {
        set type [lindex $token 3]
        set line [lindex $token 1]
        
        if {$type == "class" || $type == "struct"} {
            lappend machines [createMachine "beforeLeftBrace"]
        }
        
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                if {$state == "beforeLeftBrace"} {
                    if {$type == "leftbrace"} {
                        set state "root"
                    } elseif {$type == "semicolon"} {
                        set keepMachine 0
                    }
                } elseif {$state == "root"} {
                    if {$prev2 != "virtual" && $prev1 == "compl" && $type == "identifier"} {
                        set dtorName [lindex $token 0]
                        report $fileName $line "The destructor ~${dtorName}() of the class should be virtual"
                    }
                    
                    if {$type == "leftbrace"} {
                        incr bracesCounter
                        set state "consumeBraces"
                    } elseif {$type == "rightbrace"} {
                        set keepMachine 0
                    }
                } elseif {$state == "consumeBraces"} {
                    if {$type == "leftbrace"} {
                        incr bracesCounter
                    } elseif {$type == "rightbrace"} {
                        incr bracesCounter -1
                        if {$bracesCounter == 0} {
                            set state "root"
                        }
                    }
                }
            }
            
            if {$keepMachine} {
                lappend machinesToKeep $m
            }
        }
        set machines $machinesToKeep
        
        set prev2 $prev1
        set prev1 $type
    }
}
