include_directories(include)
FILE (GLOB_RECURSE python_provider_srcs
        include/python_providers.h
        src/python_providers.cpp
        resources/python_providers.qrc
        )

FILE (GLOB_RECURSE python_interpreter_srcs
        include/python_interpreter.h
        src/python_interpreter.cpp
        )

add_library(python_interpreter ${python_interpreter_srcs})
target_link_libraries(python_interpreter PRIVATE pybind11::embed)
target_link_libraries(python_interpreter PUBLIC sciqlopcore)
target_compile_definitions(python_interpreter PRIVATE QT_NO_KEYWORDS)
SET_TARGET_PROPERTIES(python_interpreter PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

add_definitions(-DQT_PLUGIN)
add_definitions(-DSCIQLOP_PLUGIN_JSON_FILE_PATH="${CMAKE_CURRENT_SOURCE_DIR}/resources/python_providers.json")
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
endif()

add_library(python_providers ${python_provider_srcs})
SET_TARGET_PROPERTIES(python_providers PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_link_libraries(python_providers PUBLIC sciqlopgui)
target_link_libraries(python_providers PRIVATE python_interpreter)

install(TARGETS python_providers
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

install(TARGETS python_interpreter
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}/SciQlop
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

include(sciqlop_tests)

