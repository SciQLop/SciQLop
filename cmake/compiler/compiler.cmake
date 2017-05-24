#
# compiler.cmake : configure the compilation flags
#

message("Compiler id: ${CMAKE_CXX_COMPILER_ID}")
IF("${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
    MESSAGE("Compiler supported")
ELSEIF("${CMAKE_CXX_COMPILER_ID}" STREQUAL "Clang")
    MESSAGE("Compiler supported")
ELSEIF("${CMAKE_CXX_COMPILER_ID}" STREQUAL "MSVC")
        INCLUDE("cmake/compiler/compiler_msvc.cmake")
ELSE()
   MESSAGE(FATAL_ERROR "Compiler not supported")
ENDIF()
