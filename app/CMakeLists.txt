include_directories(include)

FILE (GLOB_RECURSE app_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

QT5_WRAP_UI(UiGenerated_SRCS
    ui/MainWindow.ui
)

if(ENABLE_WIN32_CONSOLE)
    add_executable(sciqlopapp ${app_SRCS} ${UiGenerated_SRCS})
else()
    add_executable(sciqlopapp WIN32 ${app_SRCS} ${UiGenerated_SRCS})
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

install(TARGETS sciqlopapp DESTINATION ${CMAKE_INSTALL_BINDIR})
install(FILES resources/SciQLOP.desktop DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/applications/)
install(FILES resources/SciQLOP.appdata.xml DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/metainfo/)
install(FILES resources/sciqlopLOGO.svg DESTINATION ${CMAKE_INSTALL_DATAROOTDIR}/SciQLOP/icons/)


