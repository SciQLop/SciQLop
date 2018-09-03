include_directories(include)
FILE (GLOB_RECURSE genericWS_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

add_definitions(-DQT_PLUGIN)
add_definitions(-DSCIQLOP_PLUGIN_JSON_FILE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/resources/genericWS.json")
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
endif()

add_library(generic_ws ${genericWS_SRCS})
SET_TARGET_PROPERTIES(generic_ws PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_link_libraries(generic_ws PUBLIC sciqlopgui)

install(TARGETS generic_ws
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

include(sciqlop_tests)

