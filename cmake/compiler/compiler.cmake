#
# compiler.cmake : configure the compilation flags
#

IF(${CMAKE_CXX_COMPILER_ID} STREQUAL "GNU")
	INCLUDE("cmake/compiler/compiler_gnu.cmake")	
ELSEIF(${CMAKE_CXX_COMPILER_ID} STREQUAL "MSVC")
	INCLUDE("cmake/compiler/compiler_msvc.cmake")	
ELSE()
   MESSAGE(FATAL_ERROR "Compiler not supported")
ENDIF()
