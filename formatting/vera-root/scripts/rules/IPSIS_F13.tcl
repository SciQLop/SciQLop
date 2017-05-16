#!/usr/bin/tclsh
# namespace names should be recalled at the end of the namespace
# namespace mynamespace {
# } // mynamespace

proc createNamespaceDict {} {
    return [dict create state "waitingForIdentifier" identifier "" bracesCounter 0]
}

foreach fileName [getSourceFileNames] {

    set namespaces [list]
    
    foreach token [getTokens $fileName 1 0 -1 -1 {namespace identifier leftbrace rightbrace semicolon cppcomment}] {
        set type [lindex $token 3]
        
        set namespacesToKeep [list]
        foreach n $namespaces {
            set keepNamespace 1
            dict with n {
                if {$state == "waitingForIdentifier" && $type == "identifier"} {
                    set state "waitingForLeftBrace"
                    set identifier [lindex $token 0]
                } elseif {$state == "waitingForLeftBrace"} {
                    if {$type == "semicolon"} {
                        # Wasn't a namespace, remove the dict
                        set keepNamespace 0
                    } elseif {$type == "leftbrace"} {
                        set bracesCounter 0
                        set state "waitingForRightBrace"
                    }
                } elseif {$state == "waitingForRightBrace"} {
                    if {$type == "leftbrace"} {
                        incr bracesCounter
                    } elseif {$type == "rightbrace"} {
                        if {$bracesCounter > 0} {
                            incr bracesCounter -1
                        } else {
                            set state "waitingForComment"
                        }
                    }
                } elseif {$state == "waitingForComment"} {
                    if {$type == "cppcomment"} {
                        set commentValue [lindex $token 0]
                        # Check that the comment report the namespace name
                        if {![regexp "\\m$identifier\\M" $commentValue]} {
                            set line [lindex $token 1]
                            set commentValue [string trim $commentValue]
                            report $fileName $line "The namespace $identifier should have been recalled in the comment here (// $identifier). Comment found: $commentValue"
                        }
                    } else {
                        # There should have been a comment here
                        set line [lindex $token 1]
                        report $fileName $line "The namespace $identifier should have been recalled in a comment here (// $identifier)"
                    }
                    # Namespace processed, remove it from the list
                    set keepNamespace 0
                }
            }
            
            if {$keepNamespace} {
                lappend namespacesToKeep $n
            }
        }
        set namespaces $namespacesToKeep
        
        # If the token is a namespace keyword, add a namespace dict for the next
        # foreach
        if {$type == "namespace"} {
            lappend namespaces [createNamespaceDict]
        }
    }
}
