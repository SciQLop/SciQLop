
core_moc_headers = [
  'include/Data/IDataProvider.h',
  'include/DataSource/DataSourceController.h',
  'include/DataSource/DataSourceItemAction.h',
  'include/Network/NetworkController.h',
  'include/Time/TimeController.h',
  'include/Variable/Variable.h',
  'include/Variable/VariableCacheController.h',
  'include/Variable/VariableController.h',
  'include/Variable/VariableAcquisitionWorker.h',
  'include/Variable/VariableSynchronizationGroup.h',
  'include/Variable/VariableModel.h',
  'include/Visualization/VisualizationController.h'
]


core_moc_files = qt5.preprocess(moc_headers : core_moc_headers)

core_sources = [
  'src/Common/DateUtils.cpp',
  'src/Common/StringUtils.cpp',
  'src/Common/MimeTypesDef.cpp',
  'src/Data/ScalarSeries.cpp',
  'src/Data/SpectrogramSeries.cpp',
  'src/Data/DataSeriesIterator.cpp',
  'src/Data/ArrayDataIterator.cpp',
  'src/Data/VectorSeries.cpp',
  'src/Data/OptionalAxis.cpp',
  'src/Data/DataSeriesUtils.cpp',
  'src/DataSource/DataSourceController.cpp',
  'src/DataSource/DataSourceItem.cpp',
  'src/DataSource/DataSourceItemAction.cpp',
  'src/DataSource/DataSourceItemMergeHelper.cpp',
  'src/Network/NetworkController.cpp',
  'src/Plugin/PluginManager.cpp',
  'src/Settings/SqpSettingsDefs.cpp',
  'src/Time/TimeController.cpp',
  'src/Variable/Variable.cpp',
  'src/Variable/VariableCacheController.cpp',
  'src/Variable/VariableController.cpp',
  'src/Variable/VariableAcquisitionWorker.cpp',
  'src/Variable/VariableSynchronizationGroup.cpp',
  'src/Variable/VariableModel.cpp',
  'src/Visualization/VisualizationController.cpp'
]

core_inc = include_directories(['include', '../plugin/include'])

sciqlop_core_lib = library('sciqlopcore',
                       core_sources,
                       core_moc_files,
                       cpp_args : '-DCORE_LIB',
                       include_directories : core_inc,
                       dependencies : [qt5core, qt5network],
                       install : true
                       )


sciqlop_core = declare_dependency(link_with : sciqlop_core_lib,
                                include_directories : core_inc,
                                dependencies : [qt5core, qt5network])


subdir('tests')

