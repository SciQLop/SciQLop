cmake_minimum_required(VERSION 3.6)
set(SCIQLOP_VERSION 1.1.0)
project(SciQLOP
    VERSION ${SCIQLOP_VERSION}
    DESCRIPTION "SciQLOP (SCIentific Qt application for Learning from Observations of Plasmas) is an ergonomic and powerful tool enabling visualization and analysis of in situ spacecraft plasma data."
    HOMEPAGE_URL https://github.com/LaboratoryOfPlasmaPhysics/SciQLOP
    LANGUAGES CXX)

include(GNUInstallDirs)

SET(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_CURRENT_LIST_DIR}/cmake")

OPTION (CPPCHECK "Analyzes the source code with cppcheck" OFF)
OPTION (CLANG_TIDY "Analyzes the source code with Clang Tidy" OFF)
OPTION (IWYU "Analyzes the source code with Include What You Use" OFF)
OPTION (Coverage "Enables code coverage" OFF)
OPTION (BUILD_APP "Build SciQLop application" ON)
OPTION (BUILD_CORE "Build SciQLop Core module" ON)
OPTION (BUILD_GUI "Build SciQLop GUI module" ON)
OPTION (BUILD_PLUGINS "Build SciQLop plugins" ON)
OPTION (ENABLE_WIN32_CONSOLE "Enables console on Win32 platfrom" OFF)

set(CMAKE_CXX_STANDARD 17)

set(CMAKE_AUTOMOC ON)
#https://gitlab.kitware.com/cmake/cmake/issues/15227
#set(CMAKE_AUTOUIC ON)
if(POLICY CMP0071)
    cmake_policy(SET CMP0071 OLD)
endif()
set(CMAKE_AUTORCC ON)
set(CMAKE_INCLUDE_CURRENT_DIR ON)

if(NOT DEFINED CMAKE_INSTALL_RPATH_USE_LINK_PATH)
  set(CMAKE_INSTALL_RPATH_USE_LINK_PATH TRUE)
endif()
if(NOT DEFINED CMAKE_MACOSX_RPATH)
  set(CMAKE_MACOSX_RPATH TRUE)
endif()

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "" FORCE)
endif()
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O0 -g3")

find_package(Qt5 COMPONENTS Core Widgets Network PrintSupport Svg Test REQUIRED)

IF(CPPCHECK)
    set(CMAKE_CXX_CPPCHECK "cppcheck;--enable=warning,style")
ENDIF(CPPCHECK)

IF(CLANG_TIDY)
    set(CMAKE_CXX_CLANG_TIDY "clang-tidy;-style=file;-checks=*")
ENDIF(CLANG_TIDY)

IF(IWYU)
    set(CMAKE_CXX_INCLUDE_WHAT_YOU_USE "include-what-you-use")
ENDIF(IWYU)

IF(Coverage)
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_C_FLAGS_RELEASE} -g -O0 -Wall -W -Wshadow -Wunused-variable -Wunused-parameter -Wunused-function -Wunused -Wno-system-headers -Wno-deprecated -Woverloaded-virtual -Wwrite-strings -fprofile-arcs -ftest-coverage")
    set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -g -O0 -Wall -W -Wshadow -Wunused-variable \
        -Wunused-parameter -Wunused-function -Wunused -Wno-system-headers \
        -Wno-deprecated -Woverloaded-virtual -Wwrite-strings -fprofile-arcs -ftest-coverage")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -fprofile-arcs -ftest-coverage")

    add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/gcov.html
        COMMAND gcovr --exclude='.*Test.*' --exclude='.*external.*' --object-directory ${CMAKE_BINARY_DIR}  -r ${CMAKE_SOURCE_DIR}  --html  --html-details -o ${CMAKE_CURRENT_BINARY_DIR}/gcov.html
        )
    add_custom_target(gcovr
        DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/gcov.html gcovr
    )
    add_custom_target(show_coverage
        COMMAND xdg-open ${CMAKE_CURRENT_BINARY_DIR}/gcov.html
        DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/gcov.html gcovr
        )
ENDIF(Coverage)

enable_testing()

add_definitions(-DSCIQLOP_VERSION="${SCIQLOP_VERSION}")

if(BUILD_CORE)
    find_package(SciQLOPCore CONFIG QUIET)
    if (NOT SciQLOPCore_FOUND)
        if(NOT IS_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/core)
            message("Init submodule Core")
            execute_process(COMMAND git submodule init core WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
            execute_process(COMMAND git submodule update core WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
        endif()
        add_subdirectory(core)
    endif()
endif()

if(BUILD_GUI)
    add_subdirectory(gui)
endif()
if(BUILD_APP)
    add_subdirectory(app)
endif()
if(BUILD_PLUGINS)
    add_subdirectory(plugins)
endif()
#add_subdirectory(docs)
