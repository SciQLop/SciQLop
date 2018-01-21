
qxorm_dep = dependency('QxOrm', required : true, fallback:['QxOrm','qxorm_dep'])
libcatalogs_dep = dependency('libcatalogs', required : true, fallback:['libcatalogs','libcatalogs_dep'])


core_moc_headers = [
  'include/Catalogue/CatalogueController.h',
  'include/Common/SignalWaiter.h',
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
  'src/Common/SignalWaiter.cpp',
  'src/Common/StringUtils.cpp',
  'src/Common/MimeTypesDef.cpp',
  'src/Catalogue/CatalogueController.cpp',
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
  'src/PluginManager/PluginManager.cpp',
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

core_inc = include_directories(['include', 'include/Plugin'])

sciqlop_core_lib = library('sciqlopcore',
                       core_sources,
                       core_moc_files,
                       cpp_args : '-DCORE_LIB',
                       include_directories : core_inc,
                       dependencies : [qt5core, qt5network, libcatalogs_dep],
                       install : true
                       )


sciqlop_core = declare_dependency(link_with : sciqlop_core_lib,
                                include_directories : core_inc,
                                dependencies : [qt5core, qt5network, libcatalogs_dep])



subdir('tests')

