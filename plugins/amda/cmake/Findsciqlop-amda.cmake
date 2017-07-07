# - Try to find sciqlop-amda
# Once done this will define
#  SCIQLOP-AMDA_FOUND - System has sciqlop-amda
#  SCIQLOP-AMDA_INCLUDE_DIR - The sciqlop-amda include directories
#  SCIQLOP-AMDA_LIBRARIES - The libraries needed to use sciqlop-amda

if(SCIQLOP-AMDA_FOUND)
    return()
endif(SCIQLOP-AMDA_FOUND)

set(SCIQLOP-AMDA_INCLUDE_DIR ${sciqlop-amda_DIR}/../include)

set (OS_LIB_EXTENSION "so")

if(WIN32)
    set (OS_LIB_EXTENSION "dll")
endif(WIN32)
# TODO: Add Mac Support
set(SCIQLOP-AMDA_LIBRARIES_NAME "libsciqlop_amda${DEBUG_SUFFIX}.${OS_LIB_EXTENSION}")
set(SCIQLOP-AMDA_LIBRARIES "${LIBRARY_OUTPUT_PATH}/${SCIQLOP-AMDA_LIBRARIES_NAME}")

set(SCIQLOP-AMDA_FOUND TRUE)
