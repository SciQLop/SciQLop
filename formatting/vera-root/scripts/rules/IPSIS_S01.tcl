#!/usr/bin/tclsh
# At most one class per header file

foreach fileName [getSourceFileNames] {
    if {[regexp {(?:\\|/)?([^\\/]+?)\.h$} $fileName matchedExpr expectedClassName]} {
        set state "waitingForClass"
        set alreadyOneClass 0
        set firstClassName ""
        set bracesCounter 0
        
        set lastIdentifier ""
        foreach token [getTokens $fileName 1 0 -1 -1 {class identifier leftbrace rightbrace colon semicolon}] {
            set type [lindex $token 3]
            
            if {$type == "identifier"} {
                set lastIdentifier [lindex $token 0]
            }
            
            if {$state == "waitingForClass" && $type == "class"} {
                set state "waitingForBeginingOfClass"
            } elseif {$state == "waitingForBeginingOfClass"} {
                if {$type == "semicolon"} {
                    set state "waitingForClass"
                } elseif {$type == "leftbrace" || $type == "colon"} {
                    # Check if this is the first class
                    if {$alreadyOneClass} {
                        set line [lindex $token 1]
                        report $fileName $line "At most one public class can be defined in a header file. (class $lastIdentifier found but class $firstClassName already defined)"
                    } else {
                        set alreadyOneClass 1
                        set firstClassName $lastIdentifier
                        
                        # Check that the class has the same name than the file
                        if {$lastIdentifier != $expectedClassName} {
                            set line [lindex $token 1]
                            report $fileName $line "The public class should have the same name than the header file. (class $lastIdentifier found but class $expectedClassName expected)"
                        }
                    }
                    if {$type == "leftbrace"} {
                        set state "waitingForEndOfClass"
                    } else {
                        set state "waitingForLeftBrace"
                    }
                }
            } elseif {$state == "waitingForLeftBrace" && $type == "leftbrace"} {
                set state "waitingForEndOfClass"
            } elseif {$state == "waitingForEndOfClass"} {
                if {$type == "leftbrace"} {
                    incr bracesCounter
                } elseif {$type == "rightbrace"} {
                    if {$bracesCounter > 0} {
                        incr bracesCounter -1
                    } else {
                        set state "waitingForClass"
                    }
                }
            }
        }
    }
}
