#!/usr/bin/tclsh
# Naming conventions for classes and structs

set classRegex [getParameter "class-regex" {^[A-Z][A-Za-z1-9]*$}]
set structRegex [getParameter "struct-regex" {^[A-Z][A-Za-z1-9]*$}]

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
    class 
    struct 
    leftbrace 
    rightbrace 
    semicolon 
    colon 
    identifier
    comma
    assign
    rightparen
    leftbracket
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
        
        # If the type is a class or a struct, start a class/struct state machine
        if {$type == "class"} {
            lappend machines [createMachine "class" "waitingForIdentifier"]
        }
        if {$type == "struct"} {
            lappend machines [createMachine "struct" "waitingForIdentifier"]
        }
        
        set machinesToKeep [list]
        foreach m $machines {
            set keepMachine 1
            dict with m {
                # class/struct
                if {$name == "class" || $name == "struct"} {
                    # We retrieve the name of the class when we find a colon or 
                    # a leftbrace. We wait for these tokens to avoid the export 
                    # macros
                    if {$state == "waitingForIdentifier" && ($type == "colon" || $type == "leftbrace")} {
                        set state "waitingForLeftBrace"
                        set identifier $lastIdentifier
                    }
                    
                    if {$state == "waitingForLeftBrace" && $type == "leftbrace"} {
                        if {$name == "class" && ![regexp $classRegex $identifier]} {
                            report $fileName $line "The class names should match the following regex: $classRegex (found: $identifier)"
                        }
                        if {$name == "struct" && ![regexp $structRegex $identifier]} {
                            report $fileName $line "The struct names should match the following regex: $structRegex (found: $identifier)"
                        }
                    }
                    
                    if {[lsearch {semicolon leftbrace comma assign rightparen leftbracket} $type] != -1} {
                        # End of the state machine
                        set keepMachine 0
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
