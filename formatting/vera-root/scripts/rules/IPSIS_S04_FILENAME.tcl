#!/usr/bin/tclsh
# Naming conventions for file names

set fileNameRegex [getParameter "filename-regex" {^[A-Z]\w*$}]

foreach fileName [getSourceFileNames] {
    # Check file name
    if {[regexp {(?:\\|/)?([^\\/]+?)\.(?:h|cpp)$} $fileName matchedExpr fileNameWithoutExt]} {
        if {![regexp $fileNameRegex $fileNameWithoutExt]} {
            report $fileName 1 "The file names should match the following regex: $fileNameRegex (found: $fileNameWithoutExt)"
        }
    }
}
