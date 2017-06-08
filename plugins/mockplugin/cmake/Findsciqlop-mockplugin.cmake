# - Try to find sciqlop-mockplugin
# Once done this will define
#  SCIQLOP-MOCKPLUGIN_FOUND - System has sciqlop-mockplugin
#  SCIQLOP-MOCKPLUGIN_INCLUDE_DIR - The sciqlop-mockplugin include directories
#  SCIQLOP-MOCKPLUGIN_LIBRARIES - The libraries needed to use sciqlop-mockplugin

if(SCIQLOP-MOCKPLUGIN_FOUND)
    return()
endif(SCIQLOP-MOCKPLUGIN_FOUND)

set(SCIQLOP-MOCKPLUGIN_INCLUDE_DIR ${sciqlop-mockplugin_DIR}/../include)

set (OS_LIB_EXTENSION "so")

if(WIN32)
    set (OS_LIB_EXTENSION "dll")
endif(WIN32)
# TODO: Add Mac Support
set(SCIQLOP-MOCKPLUGIN_LIBRARIES ${LIBRARY_OUTPUT_PATH}/libsciqlop_mockplugin${DEBUG_SUFFIX}.${OS_LIB_EXTENSION})

set(SCIQLOP-MOCKPLUGIN_FOUND TRUE)
