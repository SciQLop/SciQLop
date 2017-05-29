#
# sciqlop_formatting.cmake
#
# Launch code formatting tools. Can be activated with ENABLE_FORMATTING and
# ENABLE_CHECKSTYLE options.
#
# The following variables are used (must be set by the cmake file calling this
# one):
#   * FORMATTING_INPUT_FILES: list of files to format;
#   * CHECKSTYLE_INPUT_FILES: list of files to check for style;
#   * CHECKSTYLE_EXCLUSION_FILES: list of vera++ exclusion files.
#

OPTION (ENABLE_FORMATTING "Format the source code while compiling" ON)
OPTION (ENABLE_CHECKSTYLE "Analyse the style of the code while compiling" ON)

IF (ENABLE_FORMATTING)
    IF (CLANGFORMAT_FOUND)
        INCLUDE(${CLANGFORMAT_USE_FILE})

        ADD_CLANGFORMAT_TARGETS(${FORMATTING_INPUT_FILES}
            ADD_TO_ALL)
    ELSE()
        MESSAGE (STATUS "Source code will not be formatted - clang-format not found")
    ENDIF()
ENDIF()

IF (ENABLE_CHECKSTYLE)
    IF (VERA++_FOUND)
        INCLUDE(${VERA++_USE_FILE})

        SET(EXCLUSIONS)
        FOREACH (e ${CHECKSTYLE_EXCLUSION_FILES})
            LIST(APPEND EXCLUSIONS EXCLUSION ${e})
        ENDFOREACH()

        message("Exclusions de vera++: ${EXCLUSIONS}")

        ADD_VERA_TARGETS(${CHECKSTYLE_INPUT_FILES}
            ADD_TO_ALL
            PROFILE "sciqlop"
            ROOT "${CMAKE_SOURCE_DIR}/formatting/vera-root"
            PARAMETER "project-name=${PROJECT_NAME}"
            ${EXCLUSIONS})

        ADD_VERA_CHECKSTYLE_TARGET(${CHECKSTYLE_INPUT_FILES}
            PROFILE "sciqlop"
            ROOT "${CMAKE_SOURCE_DIR}/formatting/vera-root"
            PARAMETER "project-name=${PROJECT_NAME}"
            ${EXCLUSIONS})

    ELSE()
        MESSAGE (STATUS "Source code will not be checkstyled - vera++ not found")
    ENDIF()
ENDIF()
