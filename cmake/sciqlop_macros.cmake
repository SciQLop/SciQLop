#
# sciqlop_macros.cmake
#
# The following functions or macros are defined in this document:
#   - SUBDIRLIST
#   - SCIQLOP_SET_TO_PARENT_SCOPE
#   - SCIQLOP_PROCESS_EXTERN_DEPENDENCIES
#	- SCIQLOP_COPY_TO_TARGET
#	- SCIQLOP_READ_FILE
#   - SCIQLOP_FIND_QT
#	- SCIQLOP_ADD_EXTERN_DEPENDENCY

#
# Define a macro to retrieve all subdirectory names of a specific directory
#
MACRO(SUBDIRLIST result curdir)
  FILE(GLOB children RELATIVE ${curdir} ${curdir}/*)
  SET(dirlist "")
  FOREACH(child ${children})
    IF(IS_DIRECTORY ${curdir}/${child})
        LIST(APPEND dirlist ${child})
    ENDIF()
  ENDFOREACH()
  SET(${result} ${dirlist})
ENDMACRO()

# SCIQLOP_SET_TO_PARENT_SCOPE(variable)
# 
# Set the given variable to the parent scope.
# 
MACRO (SCIQLOP_SET_TO_PARENT_SCOPE variable)
    SET(${variable} ${${variable}} PARENT_SCOPE)
ENDMACRO (SCIQLOP_SET_TO_PARENT_SCOPE)

MACRO(SCIQLOP_FIND_QT)
    # Find includes in corresponding build directories
    set(CMAKE_INCLUDE_CURRENT_DIR ON)
    # Instruct CMake to run moc automatically when needed.
    set(CMAKE_AUTOMOC ON)

    # Find Qt5 and the modules asked
    FOREACH(component ${ARGN})
        FIND_PACKAGE(Qt5${component} QUIET REQUIRED)
        INCLUDE_DIRECTORIES(${Qt5${component}_INCLUDE_DIRS})
    ENDFOREACH(component)
ENDMACRO(SCIQLOP_FIND_QT)

# SCIQLOP_PROCESS_EXTERN_DEPENDENCIES(externFile externLibraries externSharedLibraries)
# 
# Process the dependencies file for the modules. Each line of this file must 
# contain the parameters to pass to the FIND_PACKAGE function. This function 
# will append the libraries of the extern dependency found to the variable 
# passed as a second parameter, and add the include directories of the extern 
# dependency to the global include directories. Moreover, the extern shared 
# libraries are stored in the variable passed as a third parameter. These shared 
# libraries can then be copied to a target output path by using the 
# SCIQLOP_COPY_TO_TARGET function.
# 
# Examples:
# 
#   SCIQLOP_PROCESS_MODULE_DEPENDENCIES("path/to/extern.dependencies"
#       EXTERN_LIBRARIES
#       EXTERN_SHARED_LIBRARIES)
# 
FUNCTION (SCIQLOP_PROCESS_EXTERN_DEPENDENCIES externFile librariesVar sharedLibrariesVar)
    
    SCIQLOP_READ_FILE(${externFile} externDependencies)
    SET (externLibraries)
    SET (externSharedLibraries)
    FOREACH (externDependency ${externDependencies})
        # Check if the line is a comment (begins with #)
        STRING(REGEX MATCH "^ *#.*$" matched "${externDependency}")
        IF (NOT matched)
            STRING(REGEX REPLACE " +" ";" externDependency "${externDependency}")
            SCIQLOP_ADD_EXTERN_DEPENDENCY(externLibraries externSharedLibraries ${externDependency})
        ENDIF()
    ENDFOREACH()
    
    LIST (APPEND ${librariesVar} ${externLibraries})
    SCIQLOP_SET_TO_PARENT_SCOPE(${librariesVar})
    
    LIST (APPEND ${sharedLibrariesVar} ${externSharedLibraries})
    SCIQLOP_SET_TO_PARENT_SCOPE(${sharedLibrariesVar})
ENDFUNCTION (SCIQLOP_PROCESS_EXTERN_DEPENDENCIES)

# SCIQLOP_COPY_TO_TARGET copy the given files to the given target output path.
# 
# The first parameter must be RUNTIME or LIBRARY, and it indicates the type of 
# the target.
# 
# The second parameter is the name of the target where the files must be copied.
# The RUNTIME_OUTPUT_DIRECTORY or LIBRARY_OUTPUT_DIRECTORY target properties 
# will be used to find the output path of the copy. If these properties are 
# empty, then the EXECUTABLE_OUTPUT_PATH or LIBRARY_OUTPUT_PATH variables will 
# be used.
# 
# The rest of the parameters are the files that must be copied.
FUNCTION (SCIQLOP_COPY_TO_TARGET runtimeOrLibrary targetName)
    # Check RUNTIME or LIBRARY argument
    IF (${runtimeOrLibrary} STREQUAL "RUNTIME")
        SET (targetProperty "RUNTIME_OUTPUT_DIRECTORY")
        SET (pathProperty ${EXECUTABLE_OUTPUT_PATH})
    ELSEIF (${runtimeOrLibrary} STREQUAL "LIBRARY")
        SET (targetProperty "LIBRARY_OUTPUT_DIRECTORY")
        SET (pathProperty ${LIBRARY_OUTPUT_PATH})
    ELSE ()
        MESSAGE (FATAL "The first parameter of COPY_TO_TARGET must be either RUNTIME or LIBRARY, not \"${runtimeOrLibrary}\"")
    ENDIF ()

    # Select the output directory
    GET_TARGET_PROPERTY(OUTPUT_DIR ${targetName} ${targetProperty})
    IF (OUTPUT_DIR STREQUAL "OUTPUT_DIR-NOTFOUND")
        SET (OUTPUT_DIR ${pathProperty})
    ENDIF ()
    
    # Retrieve the list of files to copy by listing the rest of the macro 
    # arguments
    FOREACH (arg ${ARGN})
        LIST(APPEND fileList ${arg})
    ENDFOREACH()
    
    # Only copy if the list isn't empty
    IF (fileList)
        FILE(COPY ${fileList} DESTINATION ${OUTPUT_DIR})
    ENDIF()
ENDFUNCTION (SCIQLOP_COPY_TO_TARGET)

# SCIQLOP_READ_FILE(file contents)
# 
# Read the given file line by line and store the resulting list inside the 
# contents variable.
# 
# /!\ If the file contains semicolons, the macro will escape them before 
# returning the list.
# 
# From <http://public.kitware.com/pipermail/cmake/2007-May/014222.html>
FUNCTION (SCIQLOP_READ_FILE file contentsVar)
    FILE (READ ${file} contents)
    
    # Convert file contents into a CMake list (where each element in the list
    # is one line of the file)
    #
    STRING(REGEX REPLACE ";" "\\\\;" contents "${contents}")
    STRING(REGEX REPLACE "\n" ";" contents "${contents}")
    
    # Return file contents as a list
    SET (${contentsVar} "${contents}" PARENT_SCOPE)
ENDFUNCTION (SCIQLOP_READ_FILE)

# SCIQLOP_ADD_EXTERN_DEPENDENCY(externLibrariesVar externSharedLibrariesVar dependencyName [EXTRA FIND_PACKAGE ARGS])
# 
# SCIQLOP_ADD_EXTERN_DEPENDENCY can be used to add a dependency residing in the
# extern subdirectory to a module. 
# 
# The first parameter is the name of the variable where the found libraries will
# be added.
# 
# The second parameter is the name of the variable where the found shared 
# libraries will be added.
# 
# The third parameter is the name of the dependency, and the rest of the 
# arguments are the same than the FIND_PACKAGE command. In fact they are passed 
# as-is to the command.
# 
# If the dependency is found, then INCLUDE_DIRECTORIES is called for the 
# dependency include directories, and the libraries are added to the 
# externLibrariesVar variable. Moreover, if the dependency is a shared library, 
# then the dynamic libraries are added to the externSharedLibrariesVar so that 
# they can be copied and installed alongside the module. The libraries in this 
# variable are ordered so that the real library is before the symlinks to the 
# library, so that the copy and install works as expected.
FUNCTION (SCIQLOP_ADD_EXTERN_DEPENDENCY externLibrariesVar externSharedLibrariesVar dependencyName)
    STRING (TOUPPER ${dependencyName} upperDependencyName)
    
    FIND_PACKAGE(${dependencyName} ${ARGN})
    IF (${upperDependencyName}_FOUND)
        # Add the include directories of the dependency
        INCLUDE_DIRECTORIES(${${upperDependencyName}_INCLUDE_DIRS})
        
        # Add the libraries to the externLibrariesVar variable and export it to 
        # the parent scope
        LIST(APPEND ${externLibrariesVar} ${${upperDependencyName}_LIBRARIES})
        SCIQLOP_SET_TO_PARENT_SCOPE(${externLibrariesVar})

        # Find the shared libraries
        LIST(APPEND ${externSharedLibrariesVar} ${${upperDependencyName}_SHARED_LIBRARIES})
        
        # Export the externSharedLibrariesVar variable to the parent scope
        SCIQLOP_SET_TO_PARENT_SCOPE(${externSharedLibrariesVar})
    ENDIF ()
ENDFUNCTION (SCIQLOP_ADD_EXTERN_DEPENDENCY)
