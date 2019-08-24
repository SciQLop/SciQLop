find_package(PythonLibs 3 REQUIRED)
find_package(PythonInterp 3 REQUIRED)
find_package(PySide2  REQUIRED)
find_package(Shiboken2  REQUIRED)
include(PythonInfo)
find_python_site_packages(PYTHON_SITE_PACKAGES)

set(BINDINGS_SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}")
set(BINDINGS_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}")

configure_file("${BINDINGS_SRC_DIR}/bindings.xml" "${BINDINGS_BUILD_DIR}/bindings.xml" COPYONLY)
configure_file("${BINDINGS_SRC_DIR}/main.py" "${BINDINGS_BUILD_DIR}/main.py" COPYONLY)
configure_file("${BINDINGS_SRC_DIR}/TestPlugin.py" "${BINDINGS_BUILD_DIR}/plugins/TestPlugin.py" COPYONLY)

execute_process(COMMAND "${PYTHON_EXECUTABLE}" "${BINDINGS_SRC_DIR}/src_list.py" cmake "${BINDINGS_BUILD_DIR}" OUTPUT_VARIABLE BINDINGS_SOURCE)

set_property(SOURCE ${BINDINGS_SOURCE} PROPERTY SKIP_AUTOGEN ON)

list(APPEND BINDINGS_INCLUDE_DIRS
    ${PYTHON_INCLUDE_DIRS}
    ${Qt5Core_INCLUDE_DIRS}
    ${Qt5Widgets_INCLUDE_DIRS}
    ${Qt5Gui_INCLUDE_DIRS}
    ${CMAKE_CURRENT_SOURCE_DIR}/../../gui/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../core/include
    ${CMAKE_CURRENT_SOURCE_DIR}/../../core/external/TimeSeries/include
    )
list(REMOVE_DUPLICATES BINDINGS_INCLUDE_DIRS)
foreach(DIR ${BINDINGS_INCLUDE_DIRS})
    list(APPEND BINDINGS_INCLUDE_DIRS_ARGS "-I${DIR}")
endforeach()

set(SHIBOKEN_OPTIONS --generator-set=shiboken
    --enable-parent-ctor-heuristic
    --enable-return-value-heuristic
    --use-isnull-as-nb_nonzero
    --avoid-protected-hack
    --enable-pyside-extensions
    -std=c++17)
add_custom_command(
        OUTPUT ${BINDINGS_SOURCE}
        COMMAND Shiboken2::shiboken2 ${SHIBOKEN_OPTIONS}
             ${BINDINGS_INCLUDE_DIRS_ARGS}
            --typesystem-paths=${PYSIDE_TYPESYSTEMS}
            --output-directory=${CMAKE_CURRENT_BINARY_DIR}
            ${CMAKE_CURRENT_SOURCE_DIR}/bindings.h ${CMAKE_CURRENT_SOURCE_DIR}/bindings.xml

        DEPENDS "${CMAKE_CURRENT_BINARY_DIR}/bindings.xml"
        IMPLICIT_DEPENDS CXX "${CMAKE_CURRENT_SOURCE_DIR}/bindings.h"
        WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}
        COMMENT "Generating Python bindings with shiboken2")

include_directories(
    ${PYSIDE_INCLUDE_DIR}/QtCore
    ${PYSIDE_INCLUDE_DIR}/QtGui
    ${PYSIDE_INCLUDE_DIR}/QtWidgets)

include_directories(
            ${PYTHON_SITE_PACKAGES}/numpy/core/include/
            ${PYTHON_INCLUDE_DIRS}
            ${SHIBOKEN_INCLUDE_DIR}
            ${PYSIDE_INCLUDE_DIR}
            ${PYSIDE_INCLUDE_DIR}/QtCore
            ${PYSIDE_INCLUDE_DIR}/QtGui
            ${PYSIDE_INCLUDE_DIR}/QtWidgets)

add_library(SciQLopBindings MODULE ${BINDINGS_SOURCE} numpy_wrappers.h PyDataProvider.h)
set_target_properties(
    SciQLopBindings
    PROPERTIES
        PREFIX ""
        OUTPUT_NAME "SciQLopBindings"
    )
target_link_libraries(SciQLopBindings sciqlopapp)
target_link_libraries(SciQLopBindings Shiboken2::libshiboken)
target_link_libraries(SciQLopBindings PySide2::pyside2)

add_executable(debug_sciqlop_app main.cpp )
find_package (Python3 COMPONENTS Development)
target_link_libraries(debug_sciqlop_app PRIVATE Python3::Python)
