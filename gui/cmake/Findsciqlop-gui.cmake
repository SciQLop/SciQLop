# - Try to find sciqlop-gui
# Once done this will define
#  SCIQLOP-GUI_FOUND - System has sciqlop-gui
#  SCIQLOP-GUI_INCLUDE_DIR - The sciqlop-gui include directories
#  SCIQLOP-GUI_LIBRARIES - The libraries needed to use sciqlop-gui

if(SCIQLOP-GUI_FOUND)
    return()
endif(SCIQLOP-GUI_FOUND)

set(SCIQLOP-GUI_INCLUDE_DIR ${sciqlop-gui_DIR}/../include)

set (OS_LIB_EXTENSION "so")

if(WIN32)
    set (OS_LIB_EXTENSION "dll")
endif(WIN32)
# TODO: Add Mac Support
set(SCIQLOP-GUI_LIBRARIES ${LIBRARY_OUTPUT_PATH}/libsciqlop_gui${DEBUG_SUFFIX}.${OS_LIB_EXTENSION})

set(SCIQLOP-GUI_FOUND TRUE)
