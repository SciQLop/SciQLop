#!/usr/bin/tclsh
# The include guards should have the form PROJECT_FILENAME_H

set projectName [string toupper [getParameter "project-name" "PROJECTNAMENOTFOUND"]]

foreach fileName [getSourceFileNames] {
    if {[regexp {(?:\\|/)?([^\\/]+?)\.h$} $fileName matchedExpr fileNameWithoutExt]} {
        set upperFileName [string toupper $fileNameWithoutExt]
        set expectedGuard "${projectName}_${upperFileName}_H"
        
        set state "waitingForIfndef"
        
        set firstInstruction 1
        set ifndefLine -1
        set prev ""
        foreach token [getTokens $fileName 1 0 -1 -1 {pp_ifndef pp_ifdef pp_if pp_include pp_define pp_undef pp_error pp_pragma pp_endif identifier}] {
            set type [lindex $token 3]
            set line [lindex $token 1]
            
            if {$firstInstruction} {
                set firstInstruction 0
                if {$type != "pp_ifndef"} {
                    report $fileName $line "The first preprocessor instruction of a header file should be the include guard of the form PROJECTNAME_FILENAME_H. (expected: $expectedGuard)"
                    break
                } else {
                    set ifndefLine $line
                }
            }
            
            if {$prev == "pp_ifndef"} {
                if {$type == "identifier"} {
                    set identifier [lindex $token 0]
                    if {$identifier != $expectedGuard} {
                        report $fileName $ifndefLine "The include guard should have the form PROJECTNAME_FILENAME_H. (Found $identifier, expected $expectedGuard)"
                    }
                } else {
                    report $fileName $ifndefLine "The first preprocessor instruction of a header file should be the include guard of the form PROJECTNAME_FILENAME_H. (expected: $expectedGuard)"
                }
                break
            }
            
            set prev $type
        }
    }
}
