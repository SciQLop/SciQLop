include_directories(include)

FILE (GLOB_RECURSE app_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

QT5_WRAP_UI(UiGenerated_SRCS
    ui/MainWindow.ui
)

add_executable(sciqlopapp WIN32 ${app_SRCS} ${UiGenerated_SRCS})
if(NOT BUILD_SHARED_LIBS)
    add_definitions(-DQT_STATICPLUGIN)
    target_link_libraries(sciqlopapp mockplugin)
    target_link_libraries(sciqlopapp amdaplugin)
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


