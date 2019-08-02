include_directories(include)

FILE (GLOB_RECURSE app_SRCS
        include/*.h
        src/MainWindow.cpp
        src/toolbar.cpp
        resources/*.qrc
        )

QT5_WRAP_UI(UiGenerated_SRCS
    ui/MainWindow.ui
)

add_library(sciqlopapp ${UiGenerated_SRCS} ${app_SRCS})

if(ENABLE_WIN32_CONSOLE)
    add_executable(sciqlop src/Main.cpp)
else()
    add_executable(sciqlop WIN32 src/Main.cpp)
endif()

if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
    if(BUILD_PLUGINS)
        #target_link_libraries(sciqlopapp mockplugin)
        #target_link_libraries(sciqlopapp amdaplugin)
        target_link_libraries(sciqlopapp python_providers)
    endif()
endif()

if(NOT BUILD_PLUGINS)
    add_definitions(-DSQP_NO_PLUGINS)
endif()

target_link_libraries(sciqlopapp
  Qt5::Core
  Qt5::Widgets
  Qt5::Network
  Qt5::PrintSupport
  Qt5::Svg
  sciqlopgui
  sciqlopcore
)

target_link_libraries(sciqlop
  sciqlopapp
)

install(TARGETS sciqlopapp
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})


install(TARGETS sciqlop DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES resources/SciQLOP.desktop DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/applications/)
install(FILES resources/SciQLOP.appdata.xml DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/metainfo/)
install(FILES resources/sciqlopLOGO.svg DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/SciQLOP/icons/)


add_subdirectory(PySide2-bindings)
