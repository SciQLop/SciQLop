#!/usr/bin/tclsh
# Naming conventions for variables

set localVariableRegex [getParameter "local-var-regex" {^[a-z][A-Za-z1-9]*$}]
set classMemberVariableRegex [getParameter "class-member-var-regex" {^m_[A-Z][A-Za-z1-9]*$}]
set structMemberVariableRegex [getParameter "struct-member-var-regex" {^[a-z][A-Za-z1-9]*$}]
set staticMemberVariableRegex [getParameter "static-member-var-regex" {^s_[A-Z][A-Za-z1-9]*$}]
set constVarRegex [getParameter "const-var-regex" {^[A-Z][A-Z1-9_]*$}]

proc createMachine {machineName initState} {
    set machine [dict create name $machineName state $initState previousState "" identifier "" bracesCounter 0 bracketCounter 0 angleBracketCounter 0]
    
    # Specific keys for the "memberVariable" type
    if {$machineName == "memberVariable"} {
        dict set machine parenCounter 0
        dict set machine isStatic 0
        dict set machine isConst 0
        dict set machine isVar 1
        dict set machine isTypedef 0
        dict set machine isInClass 0
        dict set machine classOrStruct ""
    }
    
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
    using 
    namespace 
    class 
    struct 
    enum 
    typedef 
    pp_define 
    leftbrace 
    rightbrace 
    leftparen 
    rightparen 
    leftbracket
    rightbracket
    semicolon 
    colon_colon 
    colon
    comma 
    dot 
    arrow 
    assign 
    static 
    const 
    identifier
    bool
    char
    int
    float
    double
    void
    wchart
    return
    operator
    less
    greater
}

foreach fileName [getSourceFileNames] {
    set machines [list]
    
    # Check the functions at the root of the file
    lappend machines [createMachine "method" "root"]
    
    # Check static const variables at the root of the file
    lappend machines [createMachine "memberVariable" "root"]
    
    set lastIdentifier ""
    set lastIdentifier2 ""
    set prev1 ""
    set prev2 ""
    set insideFunctionParameters 0
    set insideFunction 0
    foreach token [getTokens $fileName 1 0 -1 -1 $tokenFilter] {
        set type [lindex $token 3]
        set line [lindex $token 1]
        
        # Retrieve identifier value
        if {$type == "identifier"} {
            set lastIdentifier2 $lastIdentifier
            set lastIdentifier [lindex $token 0]
        }
        
        if {$type == "namespace"} {
            # Look for the functions in the namespace to check the local variables
            lappend machines [createMachine "method" "beforeLeftBrace"]
            # Check the static const variables inside this namespace
            lappend machines [createMachine "memberVariable" "beforeLeftBrace"]
        } elseif {$type == "class" || ($type == "struct" && !$insideFunctionParameters)} {
            # Look for the functions in the class/struct to check the local variables
            lappend machines [createMachine "method" "beforeLeftBrace"]
            # Check the static const variables inside this namespace
            set m [createMachine "memberVariable" "beforeLeftBrace"]
            dict set m isInClass 1
            dict set m classOrStruct $type
            lappend machines $m
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
                            # Check the local variables inside this function
                            set insideFunctionParameters 1
                            set insideFunction 1
                            lappend machinesToKeep [createMachine "localVariable" "beforeLeftBrace"]
                            
                        } elseif {$type == "leftbrace"} {
                            set state "consumeBraces"
                            incr bracesCounter
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
                    }
                }
                
                # Local variables
                if {$name == "localVariable"} {
                    if {$state == "beforeLeftBrace"} {
                        if {$type == "less"} {
                            set previousState $state
                            set state "consumeAngleBracket"
                            incr angleBracketCounter
                        } elseif {[isCppType $prev2 $lastIdentifier2] && $prev1 == "identifier" && ($type == "comma" || $type == "assign" || $type == "rightparen" || $type == "leftbracket")} {
                            # Check function parameters
                            if {![regexp $localVariableRegex $lastIdentifier]} {
                                report $fileName $line "The method parameter names should match the following regex: $localVariableRegex (found: $lastIdentifier)"
                            }
                        } elseif {$type == "leftbrace"} {
                            set insideFunctionParameters 0
                            set state "root"
                        } elseif {$type == "semicolon"} {
                            # End of the state machine
                            set insideFunctionParameters 0
                            set insideFunction 0
                            set keepMachine 0
                        }
                    } elseif {$state == "root"} {
                        if {$type == "leftbrace"} {
                            incr bracesCounter
                        } elseif {$type == "rightbrace"} {
                            if {$bracesCounter > 0} {
                                incr bracesCounter -1
                            } else {
                                # End of the state machine
                                set insideFunctionParameters 0
                                set insideFunction 0
                                set keepMachine 0
                            }
                        }
                        
                        if {[isCppType $prev2 $lastIdentifier2] && $prev1 == "identifier" && ($type == "assign" || $type == "semicolon" || $type == "leftparen" || $type == "leftbracket")} {
                            # Check local variable
                            if {![regexp $localVariableRegex $lastIdentifier]} {
                                report $fileName $line "The local variable names should match the following regex: $localVariableRegex (found: $lastIdentifier)"
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
                    } elseif {$state == "consumeAngleBracket"} {
                        if {$type == "less"} {
                            incr angleBracketCounter
                        } elseif {$type == "greater"} {
                            incr angleBracketCounter -1
                            if {$angleBracketCounter == 0} {
                                set state $previousState
                            }
                        }
                    }
                    
                    if {$state != "consumeBracket" && $type == "leftbracket"} {
                        set previousState $state
                        set state "consumeBracket"
                        incr bracketCounter
                    }
                }
                
                # Member and const variables
                if {$name == "memberVariable"} {
                    if {$state == "beforeLeftBrace"} {
                        if {$type == "leftbrace"} {
                            set state "root"
                        } elseif {$type == "semicolon"} {
                            set keepMachine 0
                        }
                    } elseif {$state == "root"} {
                        # is/isn't var
                        if {$type == "using" || $type == "class" || $type == "struct"} {
                            set isVar 0
                        } elseif {$type == "typedef"} {
                            set isTypedef 1
                        }
                        
                        # static/const
                        if {$type == "static"} {
                            set isStatic 1
                        } elseif {$type == "const"} {
                            set isConst 1
                        }
                        
                        if {$isVar && !$isTypedef && $prev1 == "pp_define" && $type == "identifier"} {
                            # Check defines
                            if {![regexp $constVarRegex $lastIdentifier]} {
                                report $fileName $line "The constant names should match the following regex: $constVarRegex (found: $lastIdentifier)"
                            }
                        } elseif {$isVar && !$isTypedef && $prev1 == "identifier" && ($type == "assign" || $type == "semicolon" || $type == "leftbracket")} {
                            # Check member variables
                            # Appart from the const, we don't check the member variables outside
                            # of their classes to avoid false positive
                            if {((!$isInClass && $isConst) || ($isInClass && $isStatic && $isConst)) && ![regexp $constVarRegex $lastIdentifier]} {
                                report $fileName $line "The constant names should match the following regex: $constVarRegex (found: $lastIdentifier)"
                            } elseif {$isInClass && $isStatic && !$isConst && ![regexp $staticMemberVariableRegex $lastIdentifier]} {
                                report $fileName $line "The static member variable names should match the following regex: $staticMemberVariableRegex (found: $lastIdentifier)"
                            } elseif {$isInClass && !$isStatic} {
                                if {$classOrStruct == "class" && ![regexp $classMemberVariableRegex $lastIdentifier]} {
                                    report $fileName $line "The class member variable names should match the following regex: $classMemberVariableRegex (found: $lastIdentifier)"
                                } elseif {$classOrStruct == "struct" && ![regexp $structMemberVariableRegex $lastIdentifier] && ![regexp $classMemberVariableRegex $lastIdentifier]} {
                                    report $fileName $line "The struct member variable names should match the following regex: $structMemberVariableRegex or the class member regex: $classMemberVariableRegex (found: $lastIdentifier)"
                                }
                            }
                        } elseif {$type == "leftbrace"} {
                            set state "consumeBraces"
                            incr bracesCounter
                        } elseif {$type == "leftparen"} {
                            set state "consumeParen"
                            incr parenCounter
                        } elseif {$type == "rightbrace"} {
                            # End of the state machine
                            set keepMachine 0
                        }
                        
                        if {$type == "leftbracket"} {
                            incr bracketCounter
                            set state "consumeBracket"
                        }
                        
                        # Reinit static, const and isVar
                        if {$type == "assign" || $type == "semicolon" || $type == "leftbrace"} {
                            set isStatic 0
                            set isConst 0
                            set isVar 1
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
                                set state "root"
                            }
                        }
                    } elseif {$state == "consumeParen"} {
                        if {$type == "leftparen"} {
                            incr parenCounter
                        } elseif {$type == "rightparen"} {
                            incr parenCounter -1
                            if {$parenCounter == 0} {
                                set state "root"
                            }
                        }
                    } elseif {$state == "consumeBracket"} {
                        if {$type == "leftbracket"} {
                            incr bracketCounter
                        } elseif {$type == "rightbracket"} {
                            incr bracketCounter -1
                            if {$bracketCounter == 0} {
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
