cmake_minimum_required(VERSION 3.24)
project(sciqlop_launcher VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(SCIQLOP_LAUNCHER_BUILD_TESTS "Build launcher unit tests" ON)

include(FetchContent)

# FLTK is linked statically and builds its own png/zlib/jpeg, so the only system
# dependencies left are the X11/fontconfig set on Linux (none on macOS/Windows).
set(FLTK_BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(FLTK_BUILD_TEST OFF CACHE BOOL "" FORCE)
set(FLTK_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(FLTK_BUILD_FLUID OFF CACHE BOOL "" FORCE)
set(FLTK_BUILD_FLTK_OPTIONS OFF CACHE BOOL "" FORCE)
set(FLTK_BUILD_GL OFF CACHE BOOL "" FORCE)
set(FLTK_USE_SYSTEM_LIBPNG OFF CACHE BOOL "" FORCE)
set(FLTK_USE_SYSTEM_ZLIB OFF CACHE BOOL "" FORCE)
set(FLTK_USE_SYSTEM_LIBJPEG OFF CACHE BOOL "" FORCE)

FetchContent_Declare(fltk
    URL https://github.com/fltk/fltk/releases/download/release-1.4.3/fltk-1.4.3-source.tar.gz
    URL_HASH SHA256=19725f687146610976a1a43ef448feeba212a7eca88ad5897d22f6adaf3af45b
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)

FetchContent_Declare(tomlplusplus
    GIT_REPOSITORY https://github.com/marzer/tomlplusplus.git
    GIT_TAG v3.4.0
    GIT_SHALLOW TRUE)

FetchContent_MakeAvailable(fltk tomlplusplus)

add_library(launcher_core STATIC
    src/paths.cpp
    src/manifest.cpp
    src/project.cpp
    src/launcher.cpp
    $<$<BOOL:${WIN32}>:src/process_win32.cpp>
    $<$<NOT:$<BOOL:${WIN32}>>:src/process_posix.cpp>
)
target_include_directories(launcher_core PUBLIC src)
target_link_libraries(launcher_core PUBLIC tomlplusplus::tomlplusplus)
if(NOT WIN32)
    target_link_libraries(launcher_core PUBLIC ${CMAKE_DL_LIBS})
endif()

add_executable(sciqlop-launcher WIN32 MACOSX_BUNDLE
    src/main.cpp
    src/ui_fltk.cpp
)
target_link_libraries(sciqlop-launcher PRIVATE launcher_core fltk::fltk fltk::images)

if(MSVC)
    # Static CRT: the shipped binary must not need the VC++ redistributable.
    set_property(TARGET sciqlop-launcher launcher_core
        PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

if(SCIQLOP_LAUNCHER_BUILD_TESTS)
    enable_testing()
    add_executable(launcher_tests tests/test_launcher_core.cpp)
    target_link_libraries(launcher_tests PRIVATE launcher_core)
    add_test(NAME launcher_core COMMAND launcher_tests)
endif()
