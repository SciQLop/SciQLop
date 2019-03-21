include_directories(include)
FILE (GLOB_RECURSE python_providers
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

add_definitions(-DQT_PLUGIN)
add_definitions(-DSCIQLOP_PLUGIN_JSON_FILE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/resources/python_providers.json")
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
endif()

add_library(python_providers ${python_providers})
SET_TARGET_PROPERTIES(python_providers PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_link_libraries(python_providers PUBLIC sciqlopgui)
target_link_libraries(python_providers PRIVATE pybind11::embed)
ADD_DEFINITIONS(-DQT_NO_KEYWORDS)
install(TARGETS python_providers
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

include(sciqlop_tests)

