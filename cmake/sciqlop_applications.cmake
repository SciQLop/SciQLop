#
# Sciqlop_modules.cmake
#
# Set ouptut directories
#
SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
IF (UNIX)
    SET (CONFIG_OUTPUT_PATH $ENV{HOME}/.config/QtProject)
ELSEIF(WIN32)
    SET (CONFIG_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/app/QtProject)
ELSE()
    SET (CONFIG_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
ENDIF()

if(BUILD_TESTS)
    INCLUDE ("cmake/sciqlop_code_coverage.cmake")
    APPEND_COVERAGE_COMPILER_FLAGS()
endif(BUILD_TESTS)

#
# Compile the diffents modules
#
set(sciqlop-plugin_DIR "${CMAKE_SOURCE_DIR}/plugin/cmake")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-plugin_DIR}")
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/plugin")

set(sciqlop-core_DIR "${CMAKE_SOURCE_DIR}/core/cmake")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-core_DIR}")
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/core")

set(sciqlop-gui_DIR "${CMAKE_SOURCE_DIR}/gui/cmake")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-gui_DIR}")
ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/gui")

ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/app")

OPTION (BUILD_PLUGINS "Build the plugins" OFF)
IF(BUILD_PLUGINS)
    set(sciqlop-mockplugin_DIR "${CMAKE_SOURCE_DIR}/plugins/mockplugin/cmake")
    set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-mockplugin_DIR}")
    ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/plugins/mockplugin")
ENDIF(BUILD_PLUGINS)

# LOGGER
set(QTLOGGING_INI_FILE "${CMAKE_SOURCE_DIR}/config/QtProject/qtlogging.ini")
FILE(COPY ${QTLOGGING_INI_FILE} DESTINATION ${CONFIG_OUTPUT_PATH})


#
# Code formatting
#
# Vera++ exclusion files
LIST(APPEND CHECKSTYLE_EXCLUSION_FILES ${CMAKE_CURRENT_SOURCE_DIR}/formatting/vera-exclusions/exclusions.txt)
#SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_EXCLUSION_FILES)
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
