

tests = [
  [['Data/TestDataSeries.cpp'],['test_data'],['DataSeries test']],
  [['Data/TestOneDimArrayData.cpp'],['test_1d'],['One Dim Array test']],
  [['Data/TestTwoDimArrayData.cpp'],['test_2d'],['Two Dim Array test']],
  [['DataSource/TestDataSourceController.cpp'],['test_data_source'],['DataSourceController test']],
  [['Variable/TestVariableCacheController.cpp'],['test_variable_cache'],['VariableCacheController test']],
  [['Variable/TestVariable.cpp'],['test_variable'],['Variable test']]
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          link_with : sciqlop_core,
                          include_directories : core_inc,
                          dependencies : [qt5core, qt5widgets, qt5network,qt5test])
  test(unit_test[2], test_exe)
endforeach

