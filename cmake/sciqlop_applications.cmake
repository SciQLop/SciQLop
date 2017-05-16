#
# Sciqlop_modules.cmake
#
# Set ouptut directories
#
SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/${CMAKE_BUILD_TYPE})
SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/${CMAKE_BUILD_TYPE})


#
# Compile the core
#
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/sqpcore")

#
# Compile the gui
#
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/sqpgui")

#
# Compile the app
#
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/sqpapp")

#
# Code formatting
#
INCLUDE ("cmake/sciqlop_formatting.cmake")

#
# Documentation generation
#
INCLUDE ("cmake/sciqlop_doxygen.cmake")

#
# Source code analysis
#
INCLUDE ("cmake/sciqlop_code_analysis.cmake")
