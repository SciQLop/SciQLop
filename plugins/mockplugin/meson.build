
mockplugin_moc_headers = [
  'include/MockPlugin.h'
]

mockplugin_sources = [
  'src/MockDefs.cpp',
  'src/CosinusProvider.cpp',
  'src/MockPlugin.cpp'
]

mockplugin_inc = include_directories(['include'])


gen = generator(moc,
                output  : 'moc_@BASENAME@.cpp',
                arguments : ['@INPUT@',
                 '-DPLUGIN_JSON_FILE_PATH="'+meson.source_root()+'/plugins/mockplugin/resources/mockplugin.json"',
                 '-I', meson.current_source_dir()+'/include',
                 '-I', meson.current_source_dir()+'/../../core/include/',
                 '-o', '@OUTPUT@'])

mockplugin_moc_files = gen.process(mockplugin_moc_headers)

sciqlop_mockplugin = library('mockplugin',
                       mockplugin_sources,
                       mockplugin_moc_files,
                       cpp_args : '-DMOCKPLUGIN_LIB',
                       include_directories : [mockplugin_inc],
                       dependencies : [sciqlop_core, sciqlop_gui],
                       install : true
                       )

tests = [
  [['tests/TestCosinusAcquisition.cpp'],'test_cosinus_acquisition','Cosinus Acquisition test']
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          link_with : [sciqlop_mockplugin],
                          include_directories : [mockplugin_inc],
                          cpp_args : ['-DMOCKPLUGIN_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/tests-resources"'],
                          dependencies : [sciqlop_core, sciqlop_gui, qt5test])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])], timeout: 3 * 60)
endforeach
