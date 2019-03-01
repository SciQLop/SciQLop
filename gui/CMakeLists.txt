FILE (GLOB_RECURSE gui_SRCS

    include/DataSource/DataSourceWidget.h
    include/DataSource/DataSourceTreeWidget.h
    include/DataSource/DataSourceTreeWidgetItem.h
    include/DataSource/DataSourceTreeWidgetHelper.h
    include/SqpApplication.h
    include/Common/ColorUtils.h
    include/Common/VisualizationDef.h
    include/SidePane/SqpSidePane.h
    include/Catalogue2/eventsmodel.h
    include/Catalogue2/eventstreeview.h
    include/Catalogue2/repositoriestreeview.h
    include/Catalogue2/repositoriesmodel.h
    include/Catalogue2/browser.h
    include/Catalogue2/eventeditor.h
    include/Visualization/VisualizationGraphHelper.h
    include/Visualization/VisualizationTabWidget.h
    include/Visualization/VisualizationDefs.h
    include/Visualization/QCustomPlotSynchronizer.h
    include/Visualization/QCPColorMapIterator.h
    include/Visualization/operations/GenerateVariableMenuOperation.h
    include/Visualization/operations/RemoveVariableOperation.h
    include/Visualization/operations/FindVariableOperation.h
    include/Visualization/operations/MenuBuilder.h
    include/Visualization/operations/RescaleAxeOperation.h
    include/Visualization/PlottablesRenderingUtils.h
    include/Visualization/IVisualizationWidgetVisitor.h
    include/Visualization/VisualizationGraphWidget.h
    include/Visualization/IVisualizationWidget.h
    include/Visualization/IVariableContainer.h
    include/Visualization/SqpColorScale.h
    include/Visualization/VisualizationWidget.h
    include/Visualization/VisualizationZoneWidget.h
    include/Visualization/VisualizationMultiZoneSelectionDialog.h
    include/Visualization/VisualizationGraphRenderingDelegate.h
    include/Visualization/AxisRenderingUtils.h
    include/Visualization/VisualizationSelectionZoneItem.h
    include/Visualization/VisualizationDragWidget.h
    include/Visualization/VisualizationActionManager.h
    include/Visualization/IGraphSynchronizer.h
    include/Visualization/ColorScaleEditor.h
    include/Visualization/MacScrollBarStyle.h
    include/Visualization/VisualizationSelectionZoneManager.h
    include/Visualization/qcustomplot.h
    include/Visualization/VisualizationDragDropContainer.h
    include/Visualization/VisualizationCursorItem.h
    include/Settings/SqpSettingsDialog.h
    include/Settings/SqpSettingsGeneralWidget.h
    include/Variable/VariableMenuHeaderWidget.h
    include/Variable/VariableInspectorTableView.h
    include/Variable/VariableInspectorWidget.h
    include/Variable/RenameVariableDialog.h
    include/TimeWidget/TimeWidget.h
    include/DragAndDrop/DragDropScroller.h
    include/DragAndDrop/DragDropTabSwitcher.h
    include/DragAndDrop/DragDropGuiController.h
    include/Actions/FilteringAction.h
    include/Actions/ActionsGuiController.h
    include/Actions/SelectionZoneAction.h




        src/DataSource/DataSourceTreeWidgetItem.cpp
        src/DataSource/DataSourceWidget.cpp
        src/DataSource/DataSourceTreeWidget.cpp
        src/DataSource/DataSourceTreeWidgetHelper.cpp
        src/Common/ColorUtils.cpp
        src/Common/VisualizationDef.cpp
        src/SidePane/SqpSidePane.cpp
        src/Catalogue2/eventsmodel.cpp
        src/Catalogue2/eventstreeview.cpp
        src/Catalogue2/repositoriestreeview.cpp
        src/Catalogue2/repositoriesmodel.cpp
        src/Catalogue2/browser.cpp
        src/Catalogue2/eventeditor.cpp
        src/Visualization/VisualizationDragDropContainer.cpp
        src/Visualization/VisualizationTabWidget.cpp
        src/Visualization/VisualizationWidget.cpp
        src/Visualization/MacScrollBarStyle.cpp
        src/Visualization/VisualizationCursorItem.cpp
        src/Visualization/operations/MenuBuilder.cpp
        src/Visualization/operations/RemoveVariableOperation.cpp
        src/Visualization/operations/FindVariableOperation.cpp
        src/Visualization/operations/GenerateVariableMenuOperation.cpp
        src/Visualization/operations/RescaleAxeOperation.cpp
        src/Visualization/AxisRenderingUtils.cpp
        src/Visualization/PlottablesRenderingUtils.cpp
        src/Visualization/VisualizationGraphRenderingDelegate.cpp
        src/Visualization/VisualizationSelectionZoneManager.cpp
        src/Visualization/QCPColorMapIterator.cpp
        src/Visualization/ColorScaleEditor.cpp
        src/Visualization/VisualizationGraphHelper.cpp
        src/Visualization/VisualizationGraphWidget.cpp
        src/Visualization/VisualizationDragWidget.cpp
        src/Visualization/VisualizationZoneWidget.cpp
        src/Visualization/VisualizationActionManager.cpp
        src/Visualization/VisualizationSelectionZoneItem.cpp
        src/Visualization/QCustomPlotSynchronizer.cpp
        src/Visualization/qcustomplot.cpp
        src/Visualization/VisualizationMultiZoneSelectionDialog.cpp
        src/Visualization/SqpColorScale.cpp
        src/Settings/SqpSettingsGeneralWidget.cpp
        src/Settings/SqpSettingsDialog.cpp
        src/SqpApplication.cpp
        src/Variable/VariableInspectorWidget.cpp
        src/Variable/VariableMenuHeaderWidget.cpp
        src/Variable/RenameVariableDialog.cpp
        src/Variable/VariableInspectorTableView.cpp
        src/TimeWidget/TimeWidget.cpp
        src/DragAndDrop/DragDropScroller.cpp
        src/DragAndDrop/DragDropTabSwitcher.cpp
        src/DragAndDrop/DragDropGuiController.cpp
        src/Actions/ActionsGuiController.cpp
        src/Actions/SelectionZoneAction.cpp
        src/Actions/FilteringAction.cpp

        ./resources/sqpguiresources.qrc
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
    ui/Catalogue2/browser.ui
    ui/Catalogue2/eventeditor.ui
)

add_library(sciqlopgui ${gui_SRCS} ${UiGenerated_SRCS})
SET_TARGET_PROPERTIES(sciqlopgui PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)

target_include_directories(sciqlopgui PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include/Visualization>
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

subdirs(tests)
