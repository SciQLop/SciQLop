#!/usr/bin/tclsh
# Prefer C++ includes of the C std headers (cstdio instead of stdio.h for instance)

set cStdHeaders {
    assert.h
    complex.h
    ctype.h
    errno.h
    fenv.h
    float.h
    inttypes.h
    iso646.h
    limits.h
    locale.h
    math.h
    setjmp.h
    signal.h
    stdalign.h
    stdarg.h
    stdbool.h
    stddef.h
    stdint.h
    stdio.h
    stdlib.h
    string.h
    tgmath.h
    time.h
    uchar.h
    wchar.h
    wctype.h
}

set cStdHeadersWithDifferentCppEquivalent [dict create \
    stdatomic.h atomic \
    threads.h thread \
]

set cStdHeadersWithNoCppEquivalent {
    stdnoreturn.h
}

foreach fileName [getSourceFileNames] {
    foreach token [getTokens $fileName 1 0 -1 -1 {pp_hheader}] {
        set line [lindex $token 1]
        set value [lindex $token 0]
        
        if {[regexp {^[^<]*?<(.*)>[^>]*?$} $value matched headerName]} {
            if {[lsearch $cStdHeaders $headerName] != -1} {
                set headerWithoutExt [string range $headerName 0 [expr [string length $headerName] - 3]]
                set cppHeader "c$headerWithoutExt"
                report $fileName $line "$headerName is a C include, use the equivalent C++ include <$cppHeader>"
            } elseif {[dict exists $cStdHeadersWithDifferentCppEquivalent $headerName]} {
                set cppHeader [dict get $cStdHeadersWithDifferentCppEquivalent $headerName]
                report $fileName $line "$headerName is a C include, use the equivalent C++ include <$cppHeader>"
            } elseif {[lsearch $cStdHeadersWithNoCppEquivalent $headerName] != -1} {
                report $fileName $line "$headerName is a C include without C++ equivalent. Use the C++ constructions instead of relying on C headers."
            }
        }
    }
}
