
amdaplugin_moc_headers = [
  'include/AmdaPlugin.h'
]

amdaplugin_sources = [
  'src/AmdaDefs.cpp',
  'src/AmdaParser.cpp',
  'src/AmdaPlugin.cpp',
  'src/AmdaProvider.cpp',
  'src/AmdaResultParser.cpp'
]

amdaplugin_ui_files = []
amdaplugin_resources_files = [
  'resources/amdaresources.qrc'
]

amdaplugin_inc = include_directories(['include', '../../plugin/include'])

gen = generator(moc,
                output  : 'moc_@BASENAME@.cpp',
                arguments : ['@INPUT@',
                 '-DPLUGIN_JSON_FILE_PATH="'+meson.source_root()+'/plugins/amda/resources/amda.json"',
                 '-I', meson.current_source_dir()+'/include',
                 '-I', meson.current_source_dir()+'/../../plugin/include',
                 '-o', '@OUTPUT@'])

amdaplugin_moc_plugin_files = gen.process(amdaplugin_moc_headers)

amdaplugin_moc_files = qt5.preprocess(
                               ui_files : amdaplugin_ui_files,
                               qresources : amdaplugin_resources_files)

sciqlop_amdaplugin = library('amdaplugin',
                       amdaplugin_sources,
                       amdaplugin_moc_files,
                       amdaplugin_moc_plugin_files,
                       cpp_args : '-DAMDA_LIB',
                       link_with : [sciqlop_core, sciqlop_gui],
                       include_directories : [amdaplugin_inc, core_inc, gui_inc],
                       dependencies : [qt5core, qt5gui, qt5widgets, qt5network],
                       install : true
                       )


tests = [
  [['tests/TestAmdaParser.cpp'],'test_amda_parser','AMDA parser test'],
  [['tests/TestAmdaResultParser.cpp'],'test_amda_result_parser','AMDA result parser test'],
  [['tests/TestAmdaAcquisition.cpp'],'test_amda_acquisition','AMDA Acquisition test']
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          link_with : [sciqlop_core, sciqlop_amdaplugin, sciqlop_gui],
                          include_directories : [core_inc, amdaplugin_inc, gui_inc],
                          cpp_args : ['-DAMDA_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/tests-resources"'],
                          dependencies : [qt5core, qt5widgets, qt5network,qt5test])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])], timeout: 3 * 60)
endforeach
