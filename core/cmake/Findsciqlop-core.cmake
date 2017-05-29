# - Try to find sciqlop-core
# Once done this will define
#  SCIQLOP-CORE_FOUND - System has sciqlop-core
#  SCIQLOP-CORE_INCLUDE_DIR - The sciqlop-core include directories
#  SCIQLOP-CORE_LIBRARIES - The libraries needed to use sciqlop-core

if(SCIQLOP-CORE_FOUND)
    return()
endif(SCIQLOP-CORE_FOUND)

set(SCIQLOP-CORE_INCLUDE_DIR ${sciqlop-core_DIR}/../include)

set (OS_LIB_EXTENSION "so")

if(WIN32)
    set (OS_LIB_EXTENSION "dll")
endif(WIN32)
# TODO: Add Mac Support
set(SCIQLOP-CORE_LIBRARIES ${LIBRARY_OUTPUT_PATH}/libsciqlop_core${DEBUG_SUFFIX}.${OS_LIB_EXTENSION})

set(SCIQLOP-CORE_FOUND TRUE)
