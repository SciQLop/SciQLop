#!/usr/bin/tclsh
# Forbid public member variables

set forbidPublicMemberVarInStruct [getParameter "also-forbid-public-member-var-in-struct" 0]

proc createMachine {type initState} {
    set machine [dict create classOrStruct $type state $initState previousState "" bracesCounter 0 parenCounter 0 bracketCounter 0 isStatic 0 isTypedef 0 isRootClass 0]
    return $machine
}

set tokenFilter {
    public 
    protected 
    private 
    typedef 
    enum 
    class 
    struct 
    static 
    identifier 
    assign 
    semicolon 
    leftbrace 
    rightbrace 
    leftparen 
    rightparen
    leftbracket
    rightbracket
    operator
}

foreach fileName [getSourceFileNames] {
    if {[regexp {\.h$} $fileName]} {
        set machines [list]
        
        set rootClass 1
        set lastIdentifier ""
        set prev1 ""
        foreach token [getTokens $fileName 1 0 -1 -1 $tokenFilter] {
            set type [lindex $token 3]
            set line [lindex $token 1]
            
            if {$type == "identifier"} {
                set lastIdentifier [lindex $token 0]
            }
            
            if {$rootClass && ($type == "class" || $type == "struct")} {
                set m [createMachine $type "beforeLeftBrace"]
                dict set m isRootClass 1
                lappend machines $m
                set rootClass 0
            }
            
            set machinesToKeep [list]
            foreach m $machines {
                set keepMachine 1
                dict with m {
                    if {$state == "beforeLeftBrace"} {
                        if {$type == "leftbrace"} {
                            if {$classOrStruct == "class"} {
                                set state "root"
                            } elseif {$classOrStruct == "struct"} {
                                set state "public"
                            }
                        } elseif {$type == "semicolon"} {
                            set keepMachine 0
                            set rootClass $isRootClass
                        }
                    } elseif {$state == "root"} {
                        if {$type == "public"} {
                            set state "public"
                        } elseif {$type == "leftbrace"} {
                            incr bracesCounter
                            set previousState $state
                            set state "consumeBraces"
                        } elseif {$type == "rightbrace"} {
                            set keepMachine 0
                            set rootClass $isRootClass
                        }
                    } elseif {$state == "public"} {
                        if {$type == "class" || $type == "struct"} {
                            lappend machinesToKeep [createMachine $type "beforeLeftBrace"]
                        }
            
                        if {$type == "static"} {
                            set isStatic 1
                        }
                        if {$type == "typedef"} {
                            set isTypedef 1
                        }
                        
                        if {$prev1 == "identifier" && ($type == "assign" || $type == "semicolon" || $type == "leftbracket")} {
                            if {!$isStatic && !$isTypedef} {
                                if {($classOrStruct == "class") || ($classOrStruct == "struct" && $forbidPublicMemberVarInStruct)} {
                                    report $fileName $line "Public member variables are forbidden in $classOrStruct (found: $lastIdentifier)"
                                }
                            }
                        } elseif {$type == "protected" || $type == "private"} {
                            set isStatic 0
                            set isTypedef 0
                            set state "root"
                        } elseif {$type == "leftbrace"} {
                            incr bracesCounter
                            set previousState $state
                            set state "consumeBraces"
                        } elseif {$type == "leftparen"} {
                            incr parenCounter
                            set previousState $state
                            set state "consumeParen"
                        } elseif {$type == "rightbrace"} {
                            set keepMachine 0
                            set rootClass $isRootClass
                        }
                        
                        if {$type == "leftbracket"} {
                            incr bracketCounter
                            set previousState $state
                            set state "consumeBracket"
                        }
                        
                        if {$type == "semicolon" || $type == "leftbrace"} {
                            set isStatic 0
                        }
                        if {$type == "semicolon"} {
                            set isTypedef 0
                        }
                    } elseif {$state == "consumeBraces"} {
                        if {$type == "leftbrace"} {
                            incr bracesCounter
                        } elseif {$type == "rightbrace"} {
                            incr bracesCounter -1
                            if {$bracesCounter == 0} {
                                set state $previousState
                            }
                        }
                    } elseif {$state == "consumeParen"} {
                        if {$type == "leftparen"} {
                            incr parenCounter
                        } elseif {$type == "rightparen"} {
                            incr parenCounter -1
                            if {$parenCounter == 0} {
                                set state $previousState
                            }
                        }
                    } elseif {$state == "consumeBracket"} {
                        if {$type == "leftbracket"} {
                            incr bracketCounter
                        } elseif {$type == "rightbracket"} {
                            incr bracketCounter -1
                            if {$bracketCounter == 0} {
                                set state $previousState
                            }
                        }
                    }
                }
                
                if {$keepMachine} {
                    lappend machinesToKeep $m
                }
            }
            set machines $machinesToKeep
            
            set prev1 $type
        }
    }
}
