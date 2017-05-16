# - try to find clang-format tool
#
# Cache Variables:
#  CLANGFORMAT_ROOT_DIR
#  CLANGFORMAT_EXECUTABLE
#  CLANGFORMAT_USE_FILE
#
# Non-cache variables you might use in your CMakeLists.txt:
#  CLANGFORMAT_FOUND
#
# Requires these CMake modules:
#  FindPackageHandleStandardArgs (known included with CMake >=2.6.2)

file(TO_CMAKE_PATH "${CLANGFORMAT_ROOT_DIR}" CLANGFORMAT_ROOT_DIR)
set(CLANGFORMAT_ROOT_DIR
    "${CLANGFORMAT_ROOT_DIR}"
    CACHE
    PATH
    "Path to search for clang-format")

if(CLANGFORMAT_EXECUTABLE AND NOT EXISTS "${CLANGFORMAT_EXECUTABLE}")
    set(CLANGFORMAT_EXECUTABLE "notfound" CACHE PATH FORCE "")
endif()

# If we have a custom path, look there first.
if(CLANGFORMAT_ROOT_DIR)
    find_program(CLANGFORMAT_EXECUTABLE
        NAMES
        clang-format
        PATHS
        "${CLANGFORMAT_ROOT_DIR}"
        PATH_SUFFIXES
        bin
        NO_DEFAULT_PATH)
endif()

find_program(CLANGFORMAT_EXECUTABLE NAMES clang-format)

# Find the use file for clang-format
GET_FILENAME_COMPONENT(CLANGFORMAT_MODULE_DIR ${CMAKE_CURRENT_LIST_FILE} PATH)
SET(CLANGFORMAT_USE_FILE "${CLANGFORMAT_MODULE_DIR}/use_clangformat.cmake")

SET(CLANGFORMAT_ALL ${CLANGFORMAT_EXECUTABLE} ${CLANGFORMAT_USE_FILE})

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(ClangFormat
    DEFAULT_MSG
    CLANGFORMAT_ALL
    CLANGFORMAT_EXECUTABLE
    CLANGFORMAT_USE_FILE)

mark_as_advanced(CLANGFORMAT_EXECUTABLE)
