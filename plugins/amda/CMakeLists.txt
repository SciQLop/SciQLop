include_directories(include)
FILE (GLOB_RECURSE amdaplugin_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

add_definitions(-DQT_PLUGIN)
add_definitions(-DSCIQLOP_PLUGIN_JSON_FILE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/resources/amda.json")
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
endif()

add_library(amdaplugin ${amdaplugin_SRCS})
SET_TARGET_PROPERTIES(amdaplugin PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_link_libraries(amdaplugin PUBLIC sciqlopgui)

install(TARGETS amdaplugin
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

include(sciqlop_tests)

add_definitions(-DAMDA_TESTS_RESOURCES_DIR="${CMAKE_CURRENT_LIST_DIR}/tests-resources")

declare_test(TestAmdaParser TestAmdaParser tests/TestAmdaParser.cpp "amdaplugin;Qt5::Test")
declare_test(TestAmdaResultParser TestAmdaResultParser tests/TestAmdaResultParser.cpp "amdaplugin;Qt5::Test")
declare_test(TestAmdaAcquisition TestAmdaAcquisition tests/TestAmdaAcquisition.cpp "amdaplugin;Qt5::Test")

