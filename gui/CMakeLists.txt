FILE (GLOB_RECURSE gui_SRCS
        include/*.h
        src/*.cpp
        resources/*.qrc
        )

QT5_WRAP_UI(
    UiGenerated_SRCS
    ui/DataSource/DataSourceWidget.ui
    ui/Settings/SqpSettingsDialog.ui
    ui/Settings/SqpSettingsGeneralWidget.ui
    ui/SidePane/SqpSidePane.ui
    ui/TimeWidget/TimeWidget.ui
    ui/Variable/RenameVariableDialog.ui
    ui/Variable/VariableInspectorWidget.ui
    ui/Variable/VariableMenuHeaderWidget.ui
    ui/Visualization/ColorScaleEditor.ui
    ui/Visualization/VisualizationGraphWidget.ui
    ui/Visualization/VisualizationTabWidget.ui
    ui/Visualization/VisualizationWidget.ui
    ui/Visualization/VisualizationZoneWidget.ui
    ui/Visualization/VisualizationMultiZoneSelectionDialog.ui
    ui/Catalogue/CatalogueEventsWidget.ui
    ui/Catalogue/CatalogueExplorer.ui
    ui/Catalogue/CatalogueInspectorWidget.ui
    ui/Catalogue/CatalogueSideBarWidget.ui
)

add_library(sciqlopgui ${gui_SRCS} ${UiGenerated_SRCS})
SET_TARGET_PROPERTIES(sciqlopgui PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_include_directories(sciqlopgui PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include/SciQLOP>
    )

target_link_libraries(sciqlopgui PUBLIC
  Qt5::Widgets
  Qt5::PrintSupport
  Qt5::Svg
  sciqlopcore
)

install(TARGETS sciqlopgui EXPORT SciQLOPGuiConfig
    ARCHIVE  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    LIBRARY  DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME  DESTINATION ${CMAKE_INSTALL_BINDIR})

install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/SciQLOP)
install(EXPORT SciQLOPGuiConfig DESTINATION share/SciQLOPGui/cmake)
export(TARGETS sciqlopgui FILE SciQLOPGuiConfig.cmake)
