

tests = [
  [['Data/TestDataSeries.cpp'],'test_data','DataSeries test'],
  [['Data/TestOneDimArrayData.cpp'],'test_1d','One Dim Array test'],
  [['Data/TestTwoDimArrayData.cpp'],'test_2d','Two Dim Array test'],
  [['DataSource/TestDataSourceController.cpp'],'test_data_source','DataSourceController test'],
  [['Variable/TestVariableCacheController.cpp'],'test_variable_cache','VariableCacheController test'],
  [['Variable/TestVariableController.cpp'],'test_variable_controler','VariableController test'],
  [['Variable/TestVariable.cpp'],'test_variable','Variable test']
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          dependencies : [sciqlop_core, qt5test])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])])
endforeach

