include_directories(include)
FILE (GLOB_RECURSE amdaplugin_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )


set(AMDA_server_type hybrid CACHE STRING "AMDA server type selected at CMake configure time")

set(AMDA_SERVER_TYPE "hybrid;amdatest;localhost" CACHE STRING
  "List of possible for AMDA server type")

set_property(CACHE AMDA_server_type PROPERTY STRINGS ${AMDA_SERVER_TYPE})
add_definitions(-DSCIQLOP_AMDA_SERVER="${AMDA_server_type}")

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
declare_test(TestAmdaFuzzing TestAmdaFuzzing "tests/TestAmdaFuzzing.cpp;tests/FuzzingValidators.cpp;tests/FuzzingUtils.cpp;tests/FuzzingOperations.cpp;tests/FuzzingDefs.cpp" "amdaplugin;Qt5::Test")

pybind11_add_module(pytestamda tests/PyTestAmdaWrapper.cpp)
target_link_libraries(pytestamda PUBLIC amdaplugin)
target_link_libraries(pytestamda PUBLIC pysciqlop)


#pybind11_add_module(pytestamdalib SHARED tests/PyTestAmdaWrapper.cpp)
add_library(pytestamdalib tests/PyTestAmdaWrapper.cpp)
target_link_libraries(pytestamdalib PUBLIC pybind11::module)
target_link_libraries(pytestamdalib PUBLIC pybind11::embed)
target_link_libraries(pytestamdalib PUBLIC amdaplugin)
target_link_libraries(pytestamdalib PUBLIC pysciqlop)

GET_PROPERTY(CORE_PYTHON_PATH GLOBAL PROPERTY CORE_PYTHON_PATH)

declare_test(TestAmdaFileParserEmbed TestAmdaFileParserEmbed "tests/PyTestAmdaWrapperExe.cpp" "pytestamdalib")
target_compile_definitions(TestAmdaFileParserEmbed PRIVATE -DPYTESTAMDA_SCRIPT="${CMAKE_CURRENT_LIST_DIR}/tests/TestAmdaFileParser.py")
set_tests_properties(TestAmdaFileParserEmbed  PROPERTIES ENVIRONMENT PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}:${CORE_PYTHON_PATH})


declare_test(TestAmdaDownloadEmbed TestAmdaDownloadEmbed "tests/PyTestAmdaWrapperExe.cpp" "pytestamdalib")
target_compile_definitions(TestAmdaDownloadEmbed PRIVATE -DPYTESTAMDA_SCRIPT="${CMAKE_CURRENT_LIST_DIR}/tests/TestAmdaDownload.py")
set_tests_properties(TestAmdaDownloadEmbed  PROPERTIES ENVIRONMENT PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}:${CORE_PYTHON_PATH})


declare_test(TestAmdaMiniFuzzEmbed TestAmdaMiniFuzzEmbed "tests/PyTestAmdaWrapperExe.cpp" "pytestamdalib")
target_compile_definitions(TestAmdaMiniFuzzEmbed PRIVATE -DPYTESTAMDA_SCRIPT="${CMAKE_CURRENT_LIST_DIR}/tests/TestAmdaMiniFuzz.py")
set_tests_properties(TestAmdaMiniFuzzEmbed  PROPERTIES ENVIRONMENT PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}:${CORE_PYTHON_PATH})


find_package(PythonInterp 3 REQUIRED)

add_test(NAME TestAmdaFileParser
  COMMAND ${PYTHON_EXECUTABLE}
    ${CMAKE_CURRENT_LIST_DIR}/tests/TestAmdaFileParser.py
    TestAmdaFileParser)
set_tests_properties(TestAmdaFileParser  PROPERTIES ENVIRONMENT PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}:${CORE_PYTHON_PATH})


add_test(NAME TestAmdaDownload
  COMMAND ${PYTHON_EXECUTABLE}
    ${CMAKE_CURRENT_LIST_DIR}/tests/TestAmdaDownload.py
    TestAmdaDownload)
set_tests_properties(TestAmdaDownload  PROPERTIES ENVIRONMENT PYTHONPATH=${CMAKE_CURRENT_BINARY_DIR}:${CORE_PYTHON_PATH})
