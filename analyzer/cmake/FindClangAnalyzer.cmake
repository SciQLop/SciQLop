# - try to find scan-build tool
#
# Cache Variables:
#  CLANGANALYZER_ROOT_DIR
#  CLANGANALYZER_EXECUTABLE
#
# Non-cache variables you might use in your CMakeLists.txt:
#  CLANGANALYZER_FOUND
#
# Requires these CMake modules:
#  FindPackageHandleStandardArgs (known included with CMake >=2.6.2)

file(TO_CMAKE_PATH "${CLANGANALYZER_ROOT_DIR}" CLANGANALYZER_ROOT_DIR)
set(CLANGANALYZER_ROOT_DIR
    "${CLANGANALYZER_ROOT_DIR}"
    CACHE
    PATH
    "Path to search for scan-build")

if(CLANGANALYZER_EXECUTABLE AND NOT EXISTS "${CLANGANALYZER_EXECUTABLE}")
    set(CLANGANALYZER_EXECUTABLE "notfound" CACHE PATH FORCE "")
endif()

# If we have a custom path, look there first.
if(CLANGANALYZER_ROOT_DIR)
    find_program(CLANGANALYZER_EXECUTABLE
        NAMES
        scan-build
        PATHS
        "${CLANGANALYZER_ROOT_DIR}"
        PATH_SUFFIXES
        bin
        NO_DEFAULT_PATH)
endif()

find_program(CLANGANALYZER_EXECUTABLE NAMES scan-build)

IF(NOT("${CLANGANALYZER_EXECUTABLE}" STREQUAL ""))
	set(CLANGANALYZER_FOUND TRUE)
endif()

mark_as_advanced(CLANGANALYZER_EXECUTABLE)
