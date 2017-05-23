#
# sciqlop_code_analysis.cmake

# Launch code source analysis with CLANGANALYZER. Can be activated with the 
# ENABLE_ANALYSIS option.
# 
# The following CACHE variables are available: 
#   * CLANGANALYZER_EXTRA_ARGS: extra arguments for CLANGANALYZER; 
#   * CLANGANALYZER_OUTPUT: path to the xml report of CLANGANALYZER.
# 
# The following variables are used (must be set by the cmake file calling this 
# one):
#   * ANALYSIS_INPUT_DIRS: directories to analyze;
#   * ANALYSIS_EXCLUDE_DIRS: directories to exclude from the analysis.
#   

# 
# Analyze the source code with CLANGANALYZER
# 
OPTION (ENABLE_ANALYSIS "Analyze the source code with clang_analyze" ON)
IF (ENABLE_ANALYSIS)
    
    # Make sure CLANGANALYZER has been found, otherwise the source code can't be 
    # analyzed
    IF (CLANGANALYZER_FOUND)

	SET (CLANGANALYZER_OUTPUT "${CMAKE_BINARY_DIR}/clang-analyzer-ouput"
            CACHE STRING "Output file for the CLANGANALYZER report")
        MARK_AS_ADVANCED (CLANGANALYZER_OUTPUT)

        SET (CLANGANALYZER_EXTRA_ARGS -o ${CLANGANALYZER_OUTPUT}
            CACHE STRING "Extra arguments for CLANGANALYZER")
        MARK_AS_ADVANCED (CLANGANALYZER_EXTRA_ARGS)

        # Add the analyze target to launch CLANGANALYZER
        ADD_CUSTOM_TARGET (analyze
            COMMAND
            sh ${CMAKE_CURRENT_SOURCE_DIR}/analyzer/launch-clang-analyzer-linux.sh
            )

    ELSE (CLANGANALYZER_FOUND)
        MESSAGE (STATUS "The source code won't be analyzed - CLANGANALYZER not found")
    ENDIF (CLANGANALYZER_FOUND)
ENDIF (ENABLE_ANALYSIS)
