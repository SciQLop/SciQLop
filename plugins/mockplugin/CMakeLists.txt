include_directories(include)
FILE (GLOB_RECURSE mockplugin_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

add_definitions(-DQT_PLUGIN)
add_definitions(-DPLUGIN_JSON_FILE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/resources/mockplugin.json")
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
endif()

add_library(mockplugin ${mockplugin_SRCS})
SET_TARGET_PROPERTIES(mockplugin PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_link_libraries(mockplugin sciqlopgui)

install(TARGETS mockplugin
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

include(sciqlop_tests)

add_definitions(-DMOCKPLUGIN_TESTS_RESOURCES_DIR="${CMAKE_CURRENT_LIST_DIR}/tests-resources")

#declare_test(TestCosinusAcquisition TestCosinusAcquisition tests/TestCosinusAcquisition.cpp "mockplugin;Qt5::Test")

