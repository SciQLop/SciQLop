# - try to find vera++ tool
#
# Cache Variables:
#  VERA++_ROOT_DIR
#  VERA++_EXECUTABLE
#  VERA++_USE_FILE
#
# Non-cache variables you might use in your CMakeLists.txt:
#  VERA++_FOUND
#
# Requires these CMake modules:
#  FindPackageHandleStandardArgs (known included with CMake >=2.6.2)

file(TO_CMAKE_PATH "${VERA++_ROOT_DIR}" VERA++_ROOT_DIR)
set(VERA++_ROOT_DIR
    "${VERA++_ROOT_DIR}"
    CACHE
    PATH
    "Path to search for vera++")

if(VERA++_EXECUTABLE AND NOT EXISTS "${VERA++_EXECUTABLE}")
    set(VERA++_EXECUTABLE "notfound" CACHE PATH FORCE "")
endif()

# If we have a custom path, look there first.
if(VERA++_ROOT_DIR)
    find_program(VERA++_EXECUTABLE
        NAMES
        vera++
        PATHS
        "${VERA++_ROOT_DIR}"
        PATH_SUFFIXES
        bin
        NO_DEFAULT_PATH)
endif()

find_program(VERA++_EXECUTABLE NAMES vera++)

# Find the use file for vera
GET_FILENAME_COMPONENT(VERA++_MODULE_DIR ${CMAKE_CURRENT_LIST_FILE} PATH)
SET(VERA++_USE_FILE "${VERA++_MODULE_DIR}/use_vera++.cmake")

SET(VERA++_ALL ${VERA++_EXECUTABLE} ${VERA++_USE_FILE})

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(vera++
    DEFAULT_MSG
    VERA++_ALL
    VERA++_EXECUTABLE
    VERA++_USE_FILE)

mark_as_advanced(VERA++_EXECUTABLE)
