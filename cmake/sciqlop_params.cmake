#
# sciqlop_params : Define compilation parameters
#
# Debug or release
#
# As the "NMake Makefiles" forces by default the CMAKE_BUILD_TYPE variable to Debug, SCIQLOP_BUILD_TYPE variable is used to be sure that the debug mode is a user choice
#SET(SCIQLOP_BUILD_TYPE "Release" CACHE STRING "Choose to compile in Debug or Release mode")

#IF(SCIQLOP_BUILD_TYPE MATCHES "Debug")
#    MESSAGE (STATUS "Build in Debug")
#    SET (CMAKE_BUILD_TYPE "Debug")
#    SET (DEBUG_SUFFIX "d")
#ELSE()
#    MESSAGE (STATUS "Build in Release")
#    SET (CMAKE_BUILD_TYPE "Release")
#    SET (SCIQLOP_BUILD_TYPE "Release")
#    SET (DEBUG_SUFFIX "")
#ENDIF()

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
# Static or shared libraries
#
OPTION (BUILD_SHARED_LIBS "Build the shared libraries" ON)

# Generate position independant code (-fPIC)
SET(CMAKE_POSITION_INDEPENDENT_CODE TRUE)

#
# Configure installation directories
#
IF (UNIX)
    SET(defaultBin "bin")
    SET(defaultInc "include/sciqlop")

    # 32 or 64 bits compiler
    IF( CMAKE_SIZEOF_VOID_P EQUAL 8 )
        SET(defaultLib "lib64/sciqlop")
    ELSE()
        SET(defaultLib "lib/sciqlop")
    ENDIF()

    SET(defaultDoc "share/docs/sciqlop")
ELSE()
    SET(defaultBin "bin")
    SET(defaultInc "include/sciqlop")
    SET(defaultLib "lib/sciqlop")
    SET(defaultDoc "docs/sciqlop")
ENDIF()

SET(INSTALL_BINARY_DIR "${defaultBin}" CACHE STRING
    "Installation directory for binaries")
SET(INSTALL_LIBRARY_DIR "${defaultLib}" CACHE STRING
    "Installation directory for libraries")
SET(INSTALL_INCLUDE_DIR "${defaultInc}" CACHE STRING
    "Installation directory for headers")
SET(INSTALL_DOCUMENTATION_DIR "${defaultDoc}" CACHE STRING
    "Installation directory for documentations")
