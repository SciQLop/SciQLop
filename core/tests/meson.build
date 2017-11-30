

tests = [
  [['Common/TestStringUtils.cpp'],'test_string_utils','StringUtils test'],
  [['Data/TestScalarSeries.cpp'],'test_scalar','ScalarSeries test'],
  [['Data/TestSpectrogramSeries.cpp'],'test_spectrogram','SpectrogramSeries test'],
  [['Data/TestVectorSeries.cpp'],'test_vector','VectorSeries test'],
  [['Data/TestOneDimArrayData.cpp'],'test_1d','One Dim Array test'],
  [['Data/TestOptionalAxis.cpp'],'test_optional_axis','OptionalAxis test'],
  [['Data/TestTwoDimArrayData.cpp'],'test_2d','Two Dim Array test'],
  [['Data/TestDataSeriesUtils.cpp'],'test_dataseries_util','Data series utils test'],
  [['DataSource/TestDataSourceController.cpp'],'test_data_source','DataSourceController test'],
  [['DataSource/TestDataSourceItem.cpp'],'test_data_source_item','DataSourceItem test'],
  [['Variable/TestVariableCacheController.cpp'],'test_variable_cache','VariableCacheController test'],
  [['Variable/TestVariable.cpp'],'test_variable','Variable test'],
  [['Variable/TestVariableSync.cpp'],'test_variable_sync','Variable synchronization test']
]

amdatest_sources = [
  'Data/DataSeriesBuilders.h',
  'Data/DataSeriesBuilders.cpp',
  'Data/DataSeriesTestsUtils.h',
  'Data/DataSeriesTestsUtils.cpp',
  'DataSource/DataSourceItemBuilder.h',
  'DataSource/DataSourceItemBuilder.cpp'
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          dependencies : [sciqlop_core, qt5test],
						  cpp_args : ['-DCORE_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/../tests-resources"'],
						  sources : [amdatest_sources])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])])
endforeach

