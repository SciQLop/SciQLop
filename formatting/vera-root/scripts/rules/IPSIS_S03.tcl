#!/usr/bin/tclsh
# The macros in header files should begin with the name of the project to avoid 
# collisions

set projectName [string toupper [getParameter "project-name" "PROJECTNAMENOTFOUND"]]

foreach fileName [getSourceFileNames] {
    if {[regexp {\.h$} $fileName]} {
        
        set prev ""
        foreach token [getTokens $fileName 1 0 -1 -1 {pp_define identifier}] {
            set type [lindex $token 3]
            
            if {$prev == "pp_define" && $type == "identifier"} {
                set identifier [lindex $token 0]
                if {![regexp "^${projectName}.*$" $identifier]} {
                    set line [lindex $token 1]
                    report $fileName $line "The macros in header files should begin with the name of the project to avoid collisions. (project name: $projectName, macro found: $identifier)"
                }
            }
            
            set prev $type
        }
    }
}
