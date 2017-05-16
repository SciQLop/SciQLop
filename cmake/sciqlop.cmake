#
# sciqlop.cmake
#

#
# Update the CMAKE_MODULE_PATH to use custom FindXXX files
#
LIST( APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake/CMakeModules/")

# Include the sciqlop version file
INCLUDE("cmake/sciqlop_version.cmake")

# Include the sciqlop cmake macros
INCLUDE("cmake/sciqlop_macros.cmake")

#
# Define the project parameters
#
INCLUDE("cmake/sciqlop_params.cmake")

#
# Configure the compiler
#
INCLUDE("cmake/compiler/compiler.cmake")

#
# Find all necessary dependencies
#
INCLUDE("cmake/find_libs.cmake")

#
# Compile all applications
#
INCLUDE("cmake/sciqlop_applications.cmake")

#
# Package creation using CPack
#
INCLUDE("cmake/sciqlop_package.cmake")
