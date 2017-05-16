#!/usr/bin/tclsh
# Naming conventions for methods

set methodRegex [getParameter "method-regex" {^[a-z][A-Za-z1-9]*$}]

proc createMachine {machineName initState} {
    set machine [dict create name $machineName state $initState identifier "" bracesCounter 0 bracketCounter 0 angleBracketCounter 0]
    return $machine
}

proc isClassMacro {value} {
    set classMacroRegexp [getParameter "classmacro-regex" {}]
    set classMacros {
        "Q_OBJECT"
    }
    set isClassMacroByRegexp 0
    if {[string length $classMacroRegexp] != 0} {
        set isClassMacroByRegexp [regexp $classMacroRegexp $value]
    }
    return [expr ([lsearch $classMacros $value] != -1) || $isClassMacroByRegexp]
}

proc isCppType {type value} {
    set cppTypes {
        "bool"
        "char"
        "int"
        "float"
        "double"
        "void"
        "wchart"
        "identifier"
    }
    
    set valueIsClassMacro 0
    if {$type == "identifier"} {
        set valueIsClassMacro [isClassMacro $value]
    }
    
    return [expr ([lsearch $cppTypes $type] != -1) && !$valueIsClassMacro] 
}

set tokenFilter {
    namespace 
    class 
    struct 
    leftbrace 
    rightbrace 
    leftparen 
    rightparen 
    less
    greater
    semicolon 
    identifier
    colon_colon
    assign
    pp_define
    bool
    char
    int
    float
    double
    void
    wchart
}

foreach fileName [getSourceFileNames] {
    
    set machines [list]
    
    # Check the functions at the root of the file
    lappend machines [createMachine "method" "root"]
    
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
        
        # Start a method state machine when coming accross a namespace or a 
        # class/struct
        if {$type == "namespace" || $type == "class" || $type == "struct"} {
            lappend machines [createMachine "method" "beforeLeftBrace"]
        }
        
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                # Method
                if {$name == "method"} {
                    if {$state == "beforeLeftBrace"} {
                        if {$type == "leftbrace"} {
                            set state "root"
                        } elseif {$type == "semicolon"} {
                            set keepMachine 0
                        }
                    } elseif {$state == "root"} {
                        if {[isCppType $prev2 $lastIdentifier2] && $prev1 == "identifier" && $type == "leftparen"} {
                            if {![regexp $methodRegex $lastIdentifier]} {
                                report $fileName $line "The method names should match the following regex: $methodRegex (found: $lastIdentifier)"
                            }
                        } elseif {$type == "leftbrace"} {
                            set state "consumeBraces"
                            incr bracesCounter
                        } elseif {$type == "less"} {
                            set state "consumeAngleBracket"
                            incr angleBracketCounter
                        } elseif {$type == "rightbrace"} {
                            # End of the state machine
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
                    } elseif {$state == "consumeAngleBracket"} {
                        if {$type == "less"} {
                            incr angleBracketCounter
                        } elseif {$type == "greater"} {
                            incr angleBracketCounter -1
                            if {$angleBracketCounter == 0} {
                                set state "root"
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
