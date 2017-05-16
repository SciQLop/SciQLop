#!/usr/bin/tclsh
# Naming conventions for typedefs

set typedefRegex [getParameter "type-regex" {^[A-Z][A-Za-z1-9]*$}]

proc createMachine {machineName initState} {
    set machine [dict create name $machineName state $initState identifier "" bracesCounter 0]
    return $machine
}

set tokenFilter {
    typedef 
    leftbrace 
    rightbrace 
    semicolon 
    identifier
}

foreach fileName [getSourceFileNames] {
    
    set machines [list]
    
    set lastIdentifier ""
    set lastIdentifier2 ""
    set prev1 ""
    set prev2 ""
    foreach token [getTokens $fileName 1 0 -1 -1 $tokenFilter] {
        set type [lindex $token 3]
        set line [lindex $token 1]
        
        # Retrieve identifier value
        if {$type == "identifier"} {
            set lastIdentifier2 $lastIdentifier
            set lastIdentifier [lindex $token 0]
        }
        
        # If the type is a typedef, start a typedef state machine
        if {$type == "typedef"} {
            lappend machines [createMachine "typedef" "waitingForIdentifier"]
        }
        
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                # typedef
                if {$name == "typedef"} {
                    if {$state == "waitingForIdentifier"} {
                        if {$type == "leftbrace"} {
                            set state "consumeBraces"
                            incr bracesCounter
                        } elseif {$type == "semicolon"} {
                            if {$prev1 == "identifier"} {
                                # Check identifier
                                if {![regexp $typedefRegex $lastIdentifier]} {
                                    report $fileName $line "The typedef names should match the following regex: $typedefRegex (found: $lastIdentifier)"
                                }
                            } else {
                                # Typedef without identifier
                                report $fileName $line "A typedef should have a name"
                            }
                            # End of the state machine
                            set keepMachine 0
                        }
                    } elseif {$state == "consumeBraces"} {
                        if {$type == "leftbrace"} {
                            incr bracesCounter
                        } elseif {$type == "rightbrace"} {
                            incr bracesCounter -1
                            if {$bracesCounter == 0} {
                                set state "waitingForIdentifier"
                            }
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
