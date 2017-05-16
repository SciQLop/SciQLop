#!/usr/bin/tclsh
# Declaration order inside classes

proc createMachine {visibility initState} {
    set machine [dict create visibility $visibility state $initState waitingFor "typedef" previousState "" bracesCounter 0 isStatic 0]
    return $machine
}

proc createVisibilityMachine {} {
    set machine [dict create state "beforeLeftBrace" visibilityState "waitingForPublic" bracesCounter 0 visibility ""]
    return $machine
}

set tokenFilter {
    public
    protected
    private
    colon
    typedef
    class
    struct
    enum
    static
    const
    identifier
    operator
    assign
    semicolon
    leftbrace
    rightbrace
    leftparen
    rightparen
}

set globalOrder "The global order is public members then public slots, protected members then protected slots and private members then private slots."

foreach fileName [getSourceFileNames] {
    set machines [list]
    set visibilityMachines [list]

    set visibilityState "waitingForPublic"

    set prev1 ""
    set prev2 ""
    set lastIdentifier ""
    foreach token [getTokens $fileName 1 0 -1 -1 $tokenFilter] {
        set type [lindex $token 3]
        set line [lindex $token 1]

        if {$type == "identifier"} {
            set lastIdentifier [lindex $token 0]
        }

        if {$type == "class" || $type == "struct"} {
            lappend visibilityMachines [createVisibilityMachine]
        }

        if {$type == "colon" && ($prev1 == "public" || $prev1 == "protected" || $prev1 == "private")} {
            lappend machines [createMachine $prev1 "beforeVisibility"]
        }

        # Machines for the visibility order
        set visibilityMachinesToKeep [list]
        foreach m $visibilityMachines {
            set keepMachine 1
            dict with m {
                if {$state == "beforeLeftBrace"} {
                    if {$type == "semicolon"} {
                        set keepMachine 0
                    } elseif {$type == "leftbrace"} {
                        set state "root"
                    }
                } elseif {$state == "root"} {
                    if {$type == "public" || $type == "protected" || $type == "private"} {
                        set visibility $type
                        set state "waitingForColon"
                    } elseif {$type == "leftbrace"} {
                        incr bracesCounter
                        set state "consumeBraces"
                    } elseif {$type == "rightbrace"} {
                        set keepMachine 0
                    }
                } elseif {$state == "waitingForColon"} {
                    if {$type == "colon"} {
                        if {$visibility == "public" && $prev1 != "identifier"} {
                            if {$visibilityState == "waitingForPublicSlots"
                                    || $visibilityState == "waitingForProtected"
                                    || $visibilityState == "waitingForProtectedSlots"
                                    || $visibilityState == "waitingForPrivate"
                                    || $visibilityState == "waitingForPrivateSlots"
                                    || $visibilityState == "done"} {
                                report $fileName $line "There should be at most one public visibility and it should be at the start of the class. $globalOrder"
                            } else {
                                set visibilityState "waitingForPublicSlots"
                            }
                        } elseif {$visibility == "public" && $prev1 == "identifier" && $lastIdentifier == "slots"} {
                            if {$visibilityState == "waitingForProtected"
                                    || $visibilityState == "waitingForProtectedSlots"
                                    || $visibilityState == "waitingForPrivate"
                                    || $visibilityState == "waitingForPrivateSlots"
                                    || $visibilityState == "done"} {
                                report $fileName $line "There should be at most one public slots visibility and it should be between public and protected. $globalOrder"
                            } else {
                                set visibilityState "waitingForProtected"
                            }
                        } elseif {$visibility == "protected" && $prev1 != "identifier"} {
                            if {$visibilityState == "waitingForProtectedSlots"
                                    || $visibilityState == "waitingForPrivate"
                                    || $visibilityState == "waitingForPrivateSlots"
                                    || $visibilityState == "done"} {
                                report $fileName $line "There should be at most one protected visibility and it should be between public slots and protected slots. $globalOrder"
                            } else {
                                set visibilityState "waitingForProtectedSlots"
                            }
                        } elseif {$visibility == "protected" && $prev1 == "identifier" && $lastIdentifier == "slots"} {
                            if {$visibilityState == "waitingForPrivate"
                                    || $visibilityState == "waitingForPrivateSlots"
                                    || $visibilityState == "done"} {
                                report $fileName $line "There should be at most one protected slots visibility and it should be between protected and private. $globalOrder"
                            } else {
                                set visibilityState "waitingForPrivate"
                            }
                        } elseif {$visibility == "private" && $prev1 != "identifier"} {
                            if {$visibilityState == "waitingForPrivateSlots"
                                    || $visibilityState == "done"} {
                                report $fileName $line "There should be at most one private visibility and it should be between protected slots and private slots. $globalOrder"
                            } else {
                                set visibilityState "waitingForPrivateSlots"
                            }
                        } elseif {$visibility == "private" && $prev1 == "identifier" && $lastIdentifier == "slots"} {
                            if {$visibilityState == "done"} {
                                report $fileName $line "There should be at most one private visibility and it should be the last of the class. $globalOrder"
                            } else {
                                set visibilityState "done"
                            }
                        }

                        set state "root"
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
                lappend visibilityMachinesToKeep $m
            }
        }
        set visibilityMachines $visibilityMachinesToKeep

        # Machines for the declaration order inside a visibility
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                if {$state == "beforeVisibility" && $type == $visibility} {
                    set state "root"
                } elseif {$state == "root"} {
                    if {$type == "public" || $type == "protected" || $type == "private" || $type == "rightbrace"} {
                        # End of the state machine when we reach the next
                        # visibility block
                        set keepMachine 0
                    } else {
                        if {$type == "static"} {
                            set isStatic 1
                        }

                        if {$waitingFor == "typedef"} {
                            if {$type == "typedef"} {
                                set state "consumeUntilNextSemiColon"
                            } else {
                                set waitingFor "enum"
                            }
                        }

                        if {$waitingFor == "enum"} {
                            if {$type == "typedef"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs should be before the enums"
                            } elseif {$type == "enum"} {
                                set state "consumeUntilNextSemiColon"
                            } else {
                                set waitingFor "class/struct"
                            }
                        }

                        if {$waitingFor == "class/struct"} {
                            if {$type == "typedef" || $type == "enum"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs and enums should be before the classes/structs"
                            } elseif {$type == "class" || $type == "struct"} {
                                set state "consumeUntilNextSemiColon"
                            } else {
                                set waitingFor "staticFunc"
                            }
                        }

                        if {$waitingFor == "staticFunc"} {
                            if {$type == "typedef" || $type == "enum" || $type == "class" || $type == "struct"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs, enums, classes and structs should be before the static functions"
                            } elseif {$prev1 == "identifier"} {
                                if {$type == "leftparen"} {
                                    if {$isStatic} {
                                        set state "consumeFunction"
                                    } else {
                                        set waitingFor "method"
                                    }
                                } elseif {$type == "assign" || $type == "semicolon"} {
                                    set waitingFor "staticVar"
                                }
                            }
                        }

                        if {$waitingFor == "staticVar"} {
                            if {$type == "typedef" || $type == "enum" || $type == "class" || $type == "struct"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs, enums, classes and structs should be before the static variables"
                            } elseif {$prev1 == "identifier"} {
                                if {$type == "leftparen"} {
                                    if {$isStatic} {
                                        set state "consumeFunction"
                                        report $fileName $line "The static functions should be before the static variables"
                                    } else {
                                        set waitingFor "method"
                                    }
                                } elseif {$type == "assign" || $type == "semicolon"} {
                                    if {!$isStatic} {
                                        set waitingFor "method"
                                    }
                                    if {$type != "semicolon"} {
                                        set state "consumeUntilNextSemiColon"
                                    } else {
                                        set isStatic 0
                                    }
                                }
                            }
                        }

                        if {$waitingFor == "method"} {
                            if {$type == "typedef" || $type == "enum" || $type == "class" || $type == "struct"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs, enums, classes and structs should be before the methods"
                            } elseif {$prev2 == "identifier" && $prev1 == "operator" && $type == "assign"} {
                                # override of operator=()
                                set state "consumeFunction"
                            } elseif {$prev1 == "identifier"} {
                                if {$type == "leftparen"} {
                                    if {$isStatic} {
                                        report $fileName $line "The static functions should be before the methods"
                                    }
                                    set state "consumeFunction"
                                } elseif {$type == "assign" || $type == "semicolon"} {
                                    if {$isStatic} {
                                        report $fileName $line "The static variables should be before the methods"
                                    } else {
                                        set waitingFor "var"
                                    }
                                }
                            }
                        }

                        if {$waitingFor == "var"} {
                            if {$type == "typedef" || $type == "enum" || $type == "class" || $type == "struct"} {
                                set state "consumeUntilNextSemiColon"
                                report $fileName $line "The typedefs, enums, classes and structs should be before the variables"
                            } elseif {$prev1 == "identifier"} {
                                if {$type == "leftparen"} {
                                    if {$isStatic} {
                                        report $fileName $line "The static functions should be before the variables"
                                    } else {
                                        report $fileName $line "The methods should be before the variables"
                                    }
                                    set state "consumeFunction"
                                } elseif {$type == "assign" || $type == "semicolon"} {
                                    if {$isStatic} {
                                        report $fileName $line "The static variables should be before the variables"
                                    }
                                }
                            }
                        }
                    }
                } elseif {$state == "consumeUntilNextSemiColon"} {
                    set isStatic 0
                    if {$type == "semicolon"} {
                        set state "root"
                    } elseif {$type == "leftbrace"} {
                        incr bracesCounter
                        set previousState $state
                        set state "consumeBraces"
                    }
                } elseif {$state == "consumeFunction"} {
                    set isStatic 0
                    if {$type == "semicolon"} {
                        set state "root"
                    } elseif {$type == "leftbrace"} {
                        incr bracesCounter
                        set previousState "root"
                        set state "consumeBraces"
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