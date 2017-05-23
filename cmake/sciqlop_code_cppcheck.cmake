#
# sciqlop_code_analysis.cmake

# Launch code source analysis with cppcheck. Can be activated with the 
# ENABLE_CPPCHECK option.
# 
# The following CACHE variables are available: 
#   * CPPCHECK_EXTRA_ARGS: extra arguments for cppcheck; 
#   * CPPCHECK_OUTPUT: path to the xml report of cppcheck.
# 
# The following variables are used (must be set by the cmake file calling this 
# one):
#   * ANALYSIS_INPUT_DIRS: directories to analyze;
#   * ANALYSIS_EXCLUDE_DIRS: directories to exclude from the analysis.
#   

# 
# Analyze the source code with cppcheck
# 
OPTION (ENABLE_CPPCHECK "Analyze the source code with cppcheck" ON)
IF (ENABLE_CPPCHECK)
    
    # Make sure cppcheck has been found, otherwise the source code can't be 
    # analyzed
    IF (CPPCHECK_FOUND)
        SET (CPPCHECK_EXTRA_ARGS --inline-suppr --xml --xml-version=2 --enable="warning,style" --force -v
            CACHE STRING "Extra arguments for cppcheck")
        MARK_AS_ADVANCED (CPPCHECK_EXTRA_ARGS)

        SET (CPPCHECK_OUTPUT "${CMAKE_BINARY_DIR}/cppcheck-report.xml"
            CACHE STRING "Output file for the cppcheck report")
        MARK_AS_ADVANCED (CPPCHECK_OUTPUT)

        SET (CPPCHECK_EXCLUDE_DIRS)
        FOREACH (dir ${ANALYSIS_EXCLUDE_DIRS})
            LIST (APPEND CPPCHECK_EXCLUDE_DIRS "-i${dir}")
        ENDFOREACH ()

        # Add the analyze target to launch cppcheck
        ADD_CUSTOM_TARGET (cppcheck
            COMMAND
            ${CPPCHECK_EXECUTABLE}
            ${CPPCHECK_EXTRA_ARGS}
            ${ANALYSIS_INPUT_DIRS}
            ${CPPCHECK_EXCLUDE_DIRS}
            2> ${CPPCHECK_OUTPUT}
            )

    ELSE (CPPCHECK_FOUND)
        MESSAGE (STATUS "The source code won't be analyzed - Cppcheck not found")
    ENDIF (CPPCHECK_FOUND)
ENDIF (ENABLE_CPPCHECK)
