#!/usr/bin/tclsh
# Naming conventions for enums

set enumRegex [getParameter "enum-regex" {^[A-Z][A-Za-z1-9]*$}]

set tokenFilter {
    class 
    struct 
    enum 
    typedef 
    identifier 
    leftbrace 
    rightbrace 
    semicolon 
}

foreach fileName [getSourceFileNames] {
    
    set lastIdentifier ""
    set prev1 ""
    set prev2 ""
    foreach token [getTokens $fileName 1 0 -1 -1 $tokenFilter] {
        set type [lindex $token 3]
        set line [lindex $token 1]
        
        # Retrieve identifier value
        if {$type == "identifier"} {
            set lastIdentifier [lindex $token 0]
        }
        
        # Check enum
        if {$prev2 == "enum" && $prev1 == "identifier" && $type == "leftbrace"} {
            if {![regexp $enumRegex $lastIdentifier]} {
                report $fileName $line "The enum names should match the following regex: $enumRegex (found: $lastIdentifier)"
            }
        }
        
        set prev2 $prev1
        set prev1 $type
    }
}
