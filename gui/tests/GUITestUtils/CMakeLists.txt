FILE (GLOB_RECURSE  GUITestUtilsSources
    GUITestUtils.h
    GUITestUtils.cpp
)

add_library(GUITestUtils ${GUITestUtilsSources})
target_link_libraries(GUITestUtils Qt5::Gui Qt5::Widgets Qt5::Test sciqlopgui)
target_include_directories(GUITestUtils PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>/
)
