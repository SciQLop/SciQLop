
gui_moc_headers = [
  'include/DataSource/DataSourceWidget.h',
  'include/Settings/SqpSettingsDialog.h',
  'include/Settings/SqpSettingsGeneralWidget.h',
  'include/SidePane/SqpSidePane.h',
  'include/SqpApplication.h',
  'include/DragAndDrop/DragDropScroller.h',
  'include/DragAndDrop/DragDropTabSwitcher.h',
  'include/TimeWidget/TimeWidget.h',
  'include/Variable/VariableInspectorWidget.h',
  'include/Variable/RenameVariableDialog.h',
  'include/Visualization/qcustomplot.h',
  'include/Visualization/VisualizationGraphWidget.h',
  'include/Visualization/VisualizationTabWidget.h',
  'include/Visualization/VisualizationWidget.h',
  'include/Visualization/VisualizationZoneWidget.h',
  'include/Visualization/VisualizationDragDropContainer.h',
  'include/Visualization/VisualizationDragWidget.h',
  'include/Visualization/ColorScaleEditor.h',
  'include/Visualization/SelectionZoneAction.h'
]

gui_ui_files = [
  'ui/DataSource/DataSourceWidget.ui',
  'ui/Settings/SqpSettingsDialog.ui',
  'ui/Settings/SqpSettingsGeneralWidget.ui',
  'ui/SidePane/SqpSidePane.ui',
  'ui/TimeWidget/TimeWidget.ui',
  'ui/Variable/VariableInspectorWidget.ui',
  'ui/Variable/RenameVariableDialog.ui',
  'ui/Variable/VariableMenuHeaderWidget.ui',
  'ui/Visualization/VisualizationGraphWidget.ui',
  'ui/Visualization/VisualizationTabWidget.ui',
  'ui/Visualization/VisualizationWidget.ui',
  'ui/Visualization/VisualizationZoneWidget.ui',
  'ui/Visualization/ColorScaleEditor.ui'
]

gui_qresources = ['resources/sqpguiresources.qrc']

gui_moc_files = qt5.preprocess(moc_headers : gui_moc_headers,
                               ui_files : gui_ui_files,
                               qresources : gui_qresources)

gui_sources = [
  'src/SqpApplication.cpp',
  'src/DragAndDrop/DragDropHelper.cpp',
  'src/DragAndDrop/DragDropScroller.cpp',
  'src/DragAndDrop/DragDropTabSwitcher.cpp',
  'src/Common/ColorUtils.cpp',
  'src/Common/VisualizationDef.cpp',
  'src/DataSource/DataSourceTreeWidgetItem.cpp',
  'src/DataSource/DataSourceTreeWidgetHelper.cpp',
  'src/DataSource/DataSourceWidget.cpp',
  'src/DataSource/DataSourceTreeWidget.cpp',
  'src/Settings/SqpSettingsDialog.cpp',
  'src/Settings/SqpSettingsGeneralWidget.cpp',
  'src/SidePane/SqpSidePane.cpp',
  'src/TimeWidget/TimeWidget.cpp',
  'src/Variable/VariableInspectorWidget.cpp',
  'src/Variable/VariableInspectorTableView.cpp',
  'src/Variable/VariableMenuHeaderWidget.cpp',
  'src/Variable/RenameVariableDialog.cpp',
  'src/Visualization/VisualizationGraphHelper.cpp',
  'src/Visualization/VisualizationGraphRenderingDelegate.cpp',
  'src/Visualization/VisualizationGraphWidget.cpp',
  'src/Visualization/VisualizationTabWidget.cpp',
  'src/Visualization/VisualizationWidget.cpp',
  'src/Visualization/VisualizationZoneWidget.cpp',
  'src/Visualization/qcustomplot.cpp',
  'src/Visualization/QCustomPlotSynchronizer.cpp',
  'src/Visualization/operations/FindVariableOperation.cpp',
  'src/Visualization/operations/GenerateVariableMenuOperation.cpp',
  'src/Visualization/operations/MenuBuilder.cpp',
  'src/Visualization/operations/RemoveVariableOperation.cpp',
  'src/Visualization/operations/RescaleAxeOperation.cpp',
  'src/Visualization/VisualizationDragDropContainer.cpp',
  'src/Visualization/VisualizationDragWidget.cpp',
  'src/Visualization/AxisRenderingUtils.cpp',
  'src/Visualization/PlottablesRenderingUtils.cpp',
  'src/Visualization/MacScrollBarStyle.cpp',
  'src/Visualization/VisualizationCursorItem.cpp',
  'src/Visualization/ColorScaleEditor.cpp',
  'src/Visualization/SqpColorScale.cpp',
  'src/Visualization/QCPColorMapIterator.cpp',
  'src/Visualization/VisualizationSelectionZoneItem.cpp',
  'src/Visualization/VisualizationSelectionZoneManager.cpp',
  'src/Visualization/SelectionZoneAction.cpp',
  'src/Visualization/ActionsGuiController.cpp',
  'src/Visualization/VisualizationActionManager.cpp'
]

gui_inc = include_directories(['include'])

sciqlop_gui_lib = library('sciqlopgui',
                       gui_sources,
                       gui_moc_files,
                       include_directories : [gui_inc],
                       dependencies : [ qt5printsupport, qt5gui, qt5widgets, qt5svg, sciqlop_core],
                       install : true
                       )

sciqlop_gui = declare_dependency(link_with : sciqlop_gui_lib,
                                include_directories : gui_inc,
                                dependencies : [qt5printsupport, qt5gui, qt5widgets, qt5svg, sciqlop_core])

