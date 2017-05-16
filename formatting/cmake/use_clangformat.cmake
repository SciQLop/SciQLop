# 
# use_clangformat.cmake
# 
# The following functions are defined in this document:
# 

# ADD_CLANGFORMAT_TARGETS(<globExpression> ...
#   [ADD_TO_ALL]
#   [NAME <name>]
#   [NAME_ALL <nameall>]
#   [STYLE style]
#   [RECURSE])
#
# Two custom targets will be created:
# * format_reports is run as part of the build, and is not rerun unless one of
# the file formatted is modified (only created if ADD_TO_ALL is provided);
# * format must be explicitely called (make format) and is rerun even if the
# files to format have not been modified. To achieve this behavior, the commands
# used in this target pretend to produce a file without actually producing it.
# Because the output file is not there after the run, the command will be rerun
# again at the next target build.
#
# If ADD_TO_ALL is provided then a target will be added to the default build
# targets so that each time a source file is compiled, it is formatted with
# clang-format.
#
# NAME and NAME_ALL customize the name of the targets (format and format_reports
# by default respectively).
#
# STYLE sets the style used by clang-format (default to "file").
#
# RECURSE selects if the glob expressions should be applied recursively or not.
FUNCTION(ADD_CLANGFORMAT_TARGETS)
    # Default values
    SET(target "format")
    SET(target_all "format_all")
    SET(style "file")
    SET(recurse OFF)
    SET(addToAll OFF)
    SET(globs)
    
    # Parse the options
    MATH(EXPR lastIdx "${ARGC} - 1")
    SET(i 0)
    WHILE(i LESS ${ARGC})
        SET(arg "${ARGV${i}}")
        IF("${arg}" STREQUAL "ADD_TO_ALL")
            SET(addToAll ON)
        ELSEIF("${arg}" STREQUAL "NAME")
            clangformat_incr(i)
            SET(target "${ARGV${i}}")
        ELSEIF("${arg}" STREQUAL "NAME_ALL")
            clangformat_incr(i)
            SET(target_all "${ARGV${i}}")
        ELSEIF("${arg}" STREQUAL "STYLE")
            clangformat_incr(i)
            SET(style "${ARGV${i}}")
        ELSEIF("${arg}" STREQUAL "RECURSE")
            SET(recurse ON)
        ELSE()
            LIST(APPEND globs ${arg})
        ENDIF()
        clangformat_incr(i)
    ENDWHILE()
    
    # Retrieve source files to format
    IF(recurse)
        FILE(GLOB_RECURSE srcs ${globs})
    ELSE()
        FILE(GLOB srcs ${globs})
    ENDIF()
    
    IF(NOT CLANGFORMAT_EXECUTABLE)
        MESSAGE(FATAL_ERROR "Unable to find clang-format executable")
    ENDIF()
    
    # Format each source file with clang-format
    SET(touchedFiles)
    SET(fakedTouchedFiles)
    SET(reportNb 0)
    # Create the directory where the touched files will be saved
    SET(formatDirectory "${CMAKE_CURRENT_BINARY_DIR}/format")
    FILE(MAKE_DIRECTORY ${formatDirectory})
    FOREACH (s ${srcs})
        SET(touchedFile ${formatDirectory}/format_touchedfile_${reportNb})
        IF(addToAll)
            ADD_CUSTOM_COMMAND(
                OUTPUT ${touchedFile}
                COMMAND ${CLANGFORMAT_EXECUTABLE}
                    -style="${style}"
                    -i
                    ${s}
                # Create a file so that this command is executed only if the source
                # file is modified
                COMMAND ${CMAKE_COMMAND} -E touch ${touchedFile}
                DEPENDS ${s}
                COMMENT "Formatting code with clang-format of ${s}"
            )
        ENDIF()

        SET(fakedTouchedFile ${formatDirectory}/format_fakedtouchedfile_${reportNb})
        ADD_CUSTOM_COMMAND(
            OUTPUT ${fakedTouchedFile}
            COMMAND ${CLANGFORMAT_EXECUTABLE}
                -style="${style}"
                -i
                ${s}
            DEPENDS ${s}
            COMMENT "Formatting code with clang-format of ${s}"
        )

        LIST(APPEND touchedFiles ${touchedFile})
        LIST(APPEND fakedTouchedFiles ${fakedTouchedFile})
        clangformat_incr(reportNb)
    ENDFOREACH()
    
    # Create the custom targets that will trigger the custom command created 
    # previously
    IF(addToAll)
        ADD_CUSTOM_TARGET(${target_all} ALL DEPENDS ${touchedFiles})
    ENDIF()
    ADD_CUSTOM_TARGET(${target} DEPENDS ${fakedTouchedFiles})
    
ENDFUNCTION(ADD_CLANGFORMAT_TARGETS)

macro(clangformat_incr var_name)
  math(EXPR ${var_name} "${${var_name}} + 1")
endmacro()
