#!/usr/bin/tclsh
# Exceptions should be thrown by value and catched by reference.
# Moreover a rethrow must be done with throw;

proc createThrowMachine {line initState} {
    set machine [dict create name "throw" keywordLine $line state $initState bracesCounter 0 firstKeyword ""]
    return $machine
}

proc createCatchMachine {line initState} {
    set machine [dict create name "catch" keywordLine $line state $initState bracesCounter 0 catchedException ""]
    return $machine
}

foreach fileName [getSourceFileNames] {
    set machines [list]
    
    set lastIdentifier ""
    set prev1 ""
    set prev2 ""
    set prev3 ""
    foreach token [getTokens $fileName 1 0 -1 -1 {throw catch new leftbrace rightbrace greater and identifier rightparen semicolon}] {
        set type [lindex $token 3]
        set line [lindex $token 1]
        
        if {$type == "identifier"} {
            set lastIdentifier [lindex $token 0]
        }
        
        if {$type == "throw"} {
            lappend machines [createThrowMachine $line "beforeThrow"]
        } elseif {$type == "catch"} {
            lappend machines [createCatchMachine $line "waitingForLeftBrace"]
        }
        
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                if {$name == "throw"} {
                    if {$state == "beforeThrow" && $type == "throw"} {
                        set state "catchFirstKeyword"
                    } elseif {$state == "catchFirstKeyword"} {
                        if {$type == "semicolon"} {
                            # This is a rethrow
                            set keepMachine 0
                        } else {
                            set firstKeyword $type
                            set state "waitForEndOfThrow"
                        }
                    } elseif {$state == "waitForEndOfThrow"} {
                        if {$type == "leftbrace"} {
                            # This is an exception specification
                            set keepMachine 0
                        } elseif {$type == "semicolon"} {
                            # This is a throw, check that the first keyword isn't
                            # new or &
                            if {$firstKeyword == "new" || $firstKeyword == "and"} {
                                report $fileName $keywordLine "Exceptions should be thrown by value. Not allocated with new or dereferenced with &."
                            }
                            set keepMachine 0
                        }
                    }
                } elseif {$name == "catch"} {
                    if {$state == "waitingForLeftBrace" && $type == "leftbrace"} {
                        set state "insideCatch"
                        
                        if {$prev2 == "identifier" &&  $prev1 == "rightparen"} {
                            set catchedException $lastIdentifier
                            
                            if {$prev3 != "and"} {
                                report $fileName $keywordLine "Exceptions should be catched by reference (exception catched: $catchedException)"
                            }
                        }
                    } elseif {$state == "insideCatch"} {
                        if {$type == "leftbrace"} {
                            incr bracesCounter
                        } elseif {$type == "rightbrace"} {
                            if {$bracesCounter > 0} {
                                incr bracesCounter -1
                            } else {
                                set keepMachine 0
                            }
                        } elseif {$prev2 == "throw" && $prev1 == "identifier" && $type == "semicolon"} {
                            if {$lastIdentifier == $catchedException} {
                                report $fileName $line "Exceptions should be rethrown with 'throw;' instead of 'throw ${catchedException};'"
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
        
        set prev3 $prev2
        set prev2 $prev1
        set prev1 $type
    }
}
