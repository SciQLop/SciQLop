#!/usr/bin/tclsh
# Naming conventions for namespaces

set namespaceRegex [getParameter "namespace-regex" {^[a-z][a-z1-9]*$}]

proc createMachine {machineName initState} {
    set machine [dict create name $machineName state $initState identifier "" bracesCounter 0 bracketCounter 0 angleBracketCounter 0]
    return $machine
}

set tokenFilter {
    using 
    namespace 
    identifier
    class 
    struct 
    enum 
    typedef 
    leftbrace 
    rightbrace
}

foreach fileName [getSourceFileNames] {
    
    set machines [list]
    
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
        
        # Check namespace
        if {$prev2 == "namespace" && $prev1 == "identifier" && $type == "leftbrace"} {
            if {![regexp $namespaceRegex $lastIdentifier]} {
                report $fileName $line "The namespace names should match the following regex: $namespaceRegex (found: $lastIdentifier)"
            }
        }
        
        set prev2 $prev1
        set prev1 $type
    }
}
