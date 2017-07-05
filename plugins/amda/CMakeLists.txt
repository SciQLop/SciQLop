## amda - CMakeLists.txt
STRING(TOLOWER ${CMAKE_PROJECT_NAME} LIBRARY_PREFFIX)
SET(SQPAMDA_LIBRARY_NAME "${LIBRARY_PREFFIX}_amda${DEBUG_SUFFIX}")
SET(SOURCES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/src")
SET(INCLUDES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/include")
SET(RESOURCES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/resources")

# Include amda directory
INCLUDE_DIRECTORIES(${INCLUDES_DIR})
INCLUDE_DIRECTORIES(${RESOURCES_DIR})

#
# Find Qt modules
#
SCIQLOP_FIND_QT(Core Widgets)

#
# Find dependent libraries
# ========================

# sciqlop plugin
find_package(sciqlop-plugin)
INCLUDE_DIRECTORIES(${SCIQLOP-PLUGIN_INCLUDE_DIR})

# sciqlop core
find_package(sciqlop-core)
INCLUDE_DIRECTORIES(${SCIQLOP-CORE_INCLUDE_DIR})
list(APPEND LIBRARIES ${SCIQLOP-CORE_LIBRARIES})

# sciqlop gui
find_package(sciqlop-gui)
INCLUDE_DIRECTORIES(${SCIQLOP-GUI_INCLUDE_DIR})
list(APPEND LIBRARIES ${SCIQLOP-GUI_LIBRARIES})

# Description file
FILE (GLOB_RECURSE PLUGIN_FILE ${RESOURCES_DIR}/amda.json)

#
# Compile the library
#

ADD_DEFINITIONS(-DAMDA_LIB)

FILE (GLOB_RECURSE MODULE_SOURCES
        ${INCLUDES_DIR}/*.h
        ${SOURCES_DIR}/*.c
        ${SOURCES_DIR}/*.cpp
        ${SOURCES_DIR}/*.h
        ${PLUGIN_FILE})

ADD_LIBRARY(${SQPAMDA_LIBRARY_NAME} ${MODULE_SOURCES})
set_property(TARGET ${SQPAMDA_LIBRARY_NAME} PROPERTY CXX_STANDARD 14)
set_property(TARGET ${SQPAMDA_LIBRARY_NAME} PROPERTY CXX_STANDARD_REQUIRED ON)

INSTALL(TARGETS ${SQPAMDA_LIBRARY_NAME}
  RUNTIME DESTINATION ${INSTALL_BINARY_DIR}
  LIBRARY DESTINATION ${INSTALL_PLUGINS_LIBRARY_DIR}
  ARCHIVE DESTINATION ${INSTALL_PLUGINS_LIBRARY_DIR}
)


TARGET_LINK_LIBRARIES(${SQPAMDA_LIBRARY_NAME} ${LIBRARIES})
qt5_use_modules(${SQPAMDA_LIBRARY_NAME} Core Widgets)

add_dependencies(${SQPAMDA_LIBRARY_NAME} ${SQPPLUGIN_LIBRARY_NAME} ${SQPGUI_LIBRARY_NAME} ${SQPCORE_LIBRARY_NAME})
	
# From cmake documentation: http://www.cmake.org/cmake/help/v3.0/manual/cmake-buildsystem.7.html
# Entries in the COMPILE_DEFINITIONS are prefixed with -D or /D and added to the compile line in an unspecified order.
# The DEFINE_SYMBOL target property is also added as a compile definition as a special convenience case for SHARED and MODULE library targets
IF(BUILD_SHARED_LIBS)
        SET_TARGET_PROPERTIES(${SQPAMDA_LIBRARY_NAME} PROPERTIES COMPILE_DEFINITIONS "SCIQLOP_EXPORT")
ELSE()
        TARGET_COMPILE_DEFINITIONS(${SQPAMDA_LIBRARY_NAME} PUBLIC "SCIQLOP_STATIC_LIBRARIES")
ENDIF()

# Set the variable to parent scope so that the other projects can copy the
# dependent shared libraries
SCIQLOP_SET_TO_PARENT_SCOPE(SQPAMDA_LIBRARY_NAME)

# Copy extern shared libraries to the lib folder
SCIQLOP_COPY_TO_TARGET(LIBRARY ${SQPAMDA_LIBRARY_NAME} ${EXTERN_SHARED_LIBRARIES})

# Add the files to the list of files to be analyzed
LIST(APPEND CHECKSTYLE_INPUT_FILES ${MODULE_SOURCES})
SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_INPUT_FILES)
# Vera++ exclusion files
#LIST(APPEND CHECKSTYLE_EXCLUSION_FILES ${CMAKE_CURRENT_SOURCE_DIR}/vera-exclusions/exclusions.txt)
SCIQLOP_SET_TO_PARENT_SCOPE(CHECKSTYLE_EXCLUSION_FILES)

#
# Compile the tests
#
IF(BUILD_TESTS)
        INCLUDE_DIRECTORIES(${SOURCES_DIR})
        FILE (GLOB_RECURSE TESTS_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/Test*.cpp)
        FILE (GLOB_RECURSE TESTS_HEADERS ${CMAKE_CURRENT_SOURCE_DIR}/Test*.h)
        SET( TEST_LIBRARIES ${SQPAMDA_LIBRARY_NAME})

        FOREACH( testFile ${TESTS_SOURCES} )
                GET_FILENAME_COMPONENT( testDirectory ${testFile} DIRECTORY )
                GET_FILENAME_COMPONENT( testName ${testFile} NAME_WE )

                # Add to the list of sources files all the sources in the same
                # directory that aren't another test
                FILE (GLOB currentTestSources
                        ${testDirectory}/*.c
                        ${testDirectory}/*.cpp
                        ${testDirectory}/*.h)
                LIST (REMOVE_ITEM currentTestSources ${TESTS_SOURCES})
                # LIST (REMOVE_ITEM currentTestSources ${TESTS_HEADERS})

                ADD_EXECUTABLE(${testName} ${testFile} ${currentTestSources})
                set_property(TARGET ${testName} PROPERTY CXX_STANDARD 14)
                set_property(TARGET ${testName} PROPERTY CXX_STANDARD_REQUIRED ON)
                TARGET_LINK_LIBRARIES( ${testName} ${TEST_LIBRARIES} )
                qt5_use_modules(${testName} Test)

                ADD_TEST( NAME ${testName} COMMAND ${testName} )

                SCIQLOP_COPY_TO_TARGET(RUNTIME ${testName} ${EXTERN_SHARED_LIBRARIES})
        ENDFOREACH( testFile )

        LIST(APPEND testFilesToFormat ${TESTS_SOURCES})
        LIST(APPEND testFilesToFormat ${TESTS_HEADERS})
        LIST(APPEND FORMATTING_INPUT_FILES ${testFilesToFormat})
        SCIQLOP_SET_TO_PARENT_SCOPE(FORMATTING_INPUT_FILES)
ENDIF(BUILD_TESTS)

#
# Set the files that must be formatted by clang-format.
#
LIST (APPEND FORMATTING_INPUT_FILES ${MODULE_SOURCES})
SCIQLOP_SET_TO_PARENT_SCOPE(FORMATTING_INPUT_FILES)

#
# Set the directories that doxygen must browse to generate the
# documentation.
#
# Source directories:
LIST (APPEND DOXYGEN_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/docs")
LIST (APPEND DOXYGEN_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/src")
SCIQLOP_SET_TO_PARENT_SCOPE(DOXYGEN_INPUT_DIRS)
# Source directories to exclude from the documentation generation
#LIST (APPEND DOXYGEN_EXCLUDE_PATTERNS "${CMAKE_CURRENT_SOURCE_DIR}/path/to/subdir/*")
SCIQLOP_SET_TO_PARENT_SCOPE(DOXYGEN_EXCLUDE_PATTERNS)

#
# Set the directories with the sources to analyze and propagate the
# modification to the parent scope
#
# Source directories to analyze:
LIST (APPEND ANALYSIS_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/src")
LIST (APPEND ANALYSIS_INPUT_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/tests")
SCIQLOP_SET_TO_PARENT_SCOPE(ANALYSIS_INPUT_DIRS)
# Source directories to exclude from the analysis
#LIST (APPEND ANALYSIS_EXCLUDE_DIRS "${CMAKE_CURRENT_SOURCE_DIR}/path/to/subdir")
SCIQLOP_SET_TO_PARENT_SCOPE(ANALYSIS_EXCLUDE_DIRS)
