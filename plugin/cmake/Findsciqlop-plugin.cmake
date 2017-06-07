# - Try to find sciqlop-plugin
# Once done this will define
#  SCIQLOP-PLUGIN_FOUND - System has sciqlop-plugin
#  SCIQLOP-PLUGIN_INCLUDE_DIR - The sciqlop-plugin include directories

if(SCIQLOP-PLUGIN_FOUND)
    return()
endif(SCIQLOP-PLUGIN_FOUND)

set(SCIQLOP-PLUGIN_INCLUDE_DIR ${sciqlop-plugin_DIR}/../include)

set(SCIQLOP-PLUGIN_FOUND TRUE)
