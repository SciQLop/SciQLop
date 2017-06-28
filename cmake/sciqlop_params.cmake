#
# sciqlop_params : Define compilation parameters
#
# Debug or release
#
# As the "NMake Makefiles" forces by default the CMAKE_BUILD_TYPE variable to Debug, SCIQLOP_BUILD_TYPE variable is used to be sure that the debug mode is a user choice
#SET(SCIQLOP_BUILD_TYPE "Release" CACHE STRING "Choose to compile in Debug or Release mode")

IF(CMAKE_BUILD_TYPE MATCHES "Debug")
    SET (DEBUG_SUFFIX "d")
ELSE()
    MESSAGE (STATUS "Build in Release")
    SET (DEBUG_SUFFIX "")
ENDIF()

#
# Need to compile tests?
#
OPTION (BUILD_TESTS "Build the tests" OFF)
ENABLE_TESTING(${BUILD_TESTS})

#
# Path to the folder for sciqlop's extern libraries.
#
# When looking for an external library in sciqlop, we look to the following
# folders:
#   - The specific folder for the library (generally of the form <LIBRARY>_ROOT_DIR
#   - The global Sciqlop extern folder
#   - The system folders.
#
# If a dependency is found in the global extern folder or a specific folder for
# the library, then it is installed with the sciqlop libraries. If it is found
# in the system folders, it is not. This behavior can be overriden with the
# <LIBRARY>_COPY_SHARED_LIBRARIES flag.
#
set(SCIQLOP_EXTERN_FOLDER "${CMAKE_CURRENT_SOURCE_DIR}/extern"
    CACHE PATH "Path to the folder for sciqlop's extern libraries")
option(SCIQLOP_FORCE_UPDATE_EXT_ROOT_DIR "Force the <LIBRARY>_ROOT_DIR to be updated to the global sciqlop extern folder"
    OFF)

if (SCIQLOP_FORCE_UPDATE_EXT_ROOT_DIR)
    set(libRootDirForceValue FORCE)
else()
    set(libRootDirForceValue)
endif()

#
# Sciqlop_modules.cmake
#
# Set ouptut directories
#
IF (UNIX)
    # 32 or 64 bits compiler
    IF( CMAKE_SIZEOF_VOID_P EQUAL 8 )
        SET(defaultLib "lib64/sciqlop")
    ELSE()
        SET(defaultLib "lib/sciqlop")
    ENDIF()
    SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/bin)
    SET (CONFIG_OUTPUT_PATH $ENV{HOME}/.config/QtProject)
    SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/${defaultLib})
ELSEIF(WIN32)
    SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
    SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
    SET (CONFIG_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist/app/QtProject)
ELSE()
    SET (EXECUTABLE_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
    SET (CONFIG_OUTPUT_PATH $ENV{HOME}/.config/QtProject)
    SET (LIBRARY_OUTPUT_PATH ${CMAKE_CURRENT_BINARY_DIR}/dist)
ENDIF()


#
# Static or shared libraries
#
OPTION (BUILD_SHARED_LIBS "Build the shared libraries" ON)

# Generate position independant code (-fPIC)
SET(CMAKE_POSITION_INDEPENDENT_CODE TRUE)



# Configuration for make install

set(PROJECT_PLUGIN_PREFIX "SciQlop")

IF (UNIX)
    SET(CMAKE_INSTALL_PREFIX "/usr/local/${PROJECT_PLUGIN_PREFIX}")
    SET(defaultBin "bin")
    SET(defaultInc "include/sciqlop")

    # 32 or 64 bits compiler
    IF( CMAKE_SIZEOF_VOID_P EQUAL 8 )
        SET(defaultLib "lib64")
        SET(defaultPluginsLib "lib64/${PROJECT_PLUGIN_PREFIX}")
    ELSE()
        SET(defaultLib "lib/")
        SET(defaultPluginsLib "lib/${PROJECT_PLUGIN_PREFIX}")
    ENDIF()

    SET(defaultDoc "share/docs/${PROJECT_PLUGIN_PREFIX}")
ELSE()
    SET(defaultBin "bin")
    SET(defaultInc "include/${PROJECT_PLUGIN_PREFIX}")
    SET(defaultLib "lib")
    SET(defaultPluginsLib "lib/${PROJECT_PLUGIN_PREFIX}")
    SET(defaultDoc "docs/${PROJECT_PLUGIN_PREFIX}")
ENDIF()

SET(INSTALL_BINARY_DIR "${defaultBin}" CACHE STRING
    "Installation directory for binaries")
SET(INSTALL_LIBRARY_DIR "${defaultLib}" CACHE STRING
    "Installation directory for libraries")
SET(INSTALL_PLUGINS_LIBRARY_DIR "${defaultPluginsLib}" CACHE STRING
    "Installation directory for libraries")
SET(INSTALL_INCLUDE_DIR "${defaultInc}" CACHE STRING
    "Installation directory for headers")
SET(INSTALL_DOCUMENTATION_DIR "${defaultDoc}" CACHE STRING
    "Installation directory for documentations")


# Set the rpath when installing
SET(CMAKE_SKIP_BUILD_RPATH FALSE)
SET(CMAKE_BUILD_WITH_INSTALL_RPATH FALSE)
SET(CMAKE_INSTALL_RPATH "${CMAKE_INSTALL_PREFIX}/${INSTALL_LIBRARY_DIR}")
SET(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)

message("Install RPATH: ${CMAKE_INSTALL_PREFIX}/${INSTALL_LIBRARY_DIR}")
