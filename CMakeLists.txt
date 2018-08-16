cmake_minimum_required(VERSION 3.6)
project(SciQLOP CXX)

include(GNUInstallDirs)

SET(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_CURRENT_LIST_DIR}/cmake")

OPTION (CPPCHECK "Analyzes the source code with cppcheck" OFF)
OPTION (CLANG_TIDY "Analyzes the source code with Clang Tidy" OFF)
OPTION (IWYU "Analyzes the source code with Include What You Use" OFF)

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

enable_testing()

add_subdirectory(core)
add_subdirectory(gui)
add_subdirectory(app)
add_subdirectory(plugins)
add_subdirectory(docs)
