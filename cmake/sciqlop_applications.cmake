
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

    # Sets AMDA server that will be used during execution.
    # Available values are:
    # - "default": default AMDA server
    # - "amdatest": AMDA test server
    # - "hybrid": use both the default server and the test server (the server used is relative to each product, according to its "server" property in the JSON file)
	# - "localhost": use local AMDA server
    # Any other value will lead to the use of the default server
    ADD_DEFINITIONS(-DSCIQLOP_AMDA_SERVER="hybrid")

    set(sciqlop-amda_DIR "${CMAKE_SOURCE_DIR}/plugins/amda/cmake")
    set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${sciqlop-amda_DIR}")
    ADD_SUBDIRECTORY("${CMAKE_SOURCE_DIR}/plugins/amda")

    # Temporary target to copy to plugins dir
    find_package(sciqlop-mockplugin)
    find_package(sciqlop-amda)
    ADD_CUSTOM_TARGET(plugins
        COMMAND ${CMAKE_COMMAND} -E copy ${SCIQLOP-MOCKPLUGIN_LIBRARIES} "${LIBRARY_OUTPUT_PATH}/plugins/${SCIQLOP-MOCKPLUGIN_LIBRARIES_NAME}"
        COMMAND ${CMAKE_COMMAND} -E copy ${SCIQLOP-AMDA_LIBRARIES} "${LIBRARY_OUTPUT_PATH}/plugins/${SCIQLOP-AMDA_LIBRARIES_NAME}"
    )
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
