#
# Sciqlop_modules.cmake
#
# Set ouptut directories
#
SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/${CMAKE_BUILD_TYPE})
SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/${CMAKE_BUILD_TYPE})


#
# Compile the diffents modules
#
set(sciqlop-core_DIR "${CMAKE_SOURCE_DIR}/core/cmake")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-core_DIR}")
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/core")

set(sciqlop-gui_DIR "${CMAKE_SOURCE_DIR}/gui/cmake")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-gui_DIR}")
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/gui")

ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/app")

#
# Code formatting
#
# Vera++ exclusion files
LIST(APPEND CHECKSTYLE_EXCLUSION_FILES ${CMAKE_CURRENT_SOURCE_DIR}/formatting/vera-exclusions/exclusions.txt)
SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_EXCLUSION_FILES)
INCLUDE ("cmake/sciqlop_formatting.cmake")

#
# Documentation generation
#
INCLUDE ("cmake/sciqlop_doxygen.cmake")

#
# Source code analysis
#
INCLUDE ("cmake/sciqlop_code_analysis.cmake")
INCLUDE ("cmake/sciqlop_code_cppcheck.cmake")
