
amdaplugin_moc_headers = [
  'include/AmdaPlugin.h',
  'include/AmdaProvider.h'
]

amdaplugin_sources = [
  'src/AmdaDefs.cpp',
  'src/AmdaParser.cpp',
  'src/AmdaPlugin.cpp',
  'src/AmdaProvider.cpp',
  'src/AmdaResultParser.cpp'
  'src/AmdaResultParserDefs.cpp'
  'src/AmdaResultParserHelper.cpp'
]

amdaplugin_ui_files = []
amdaplugin_resources_files = [
  'resources/amdaresources.qrc'
]

amdaplugin_inc = include_directories(['include', '../../plugin/include'])

moc_gen = generator(moc,
                output  : 'moc_@BASENAME@.cpp',
                arguments : ['@INPUT@',
                 '-DPLUGIN_JSON_FILE_PATH="'+meson.source_root()+'/plugins/amda/resources/amda.json"',
                 '-I', meson.current_source_dir()+'/include',
                 '-I', meson.current_source_dir()+'/../../plugin/include',
                 '-o', '@OUTPUT@'])

rcc_gen = generator(rcc,
                output  : 'qrc_@BASENAME@.cpp',
                arguments : ['--name=@BASENAME@"',
                 '--output',
                 '@OUTPUT@',
                 '@INPUT@'])

amdaplugin_moc_plugin_files = moc_gen.process(amdaplugin_moc_headers)

amdaplugin_rcc_plugin_files = rcc_gen.process(amdaplugin_resources_files)

#amdaplugin_rcc_plugin_files = qt5.preprocess(
#                               qresources : amdaplugin_resources_files)

amdaplugin_moc_files = qt5.preprocess(
                               ui_files : amdaplugin_ui_files)

sciqlop_amdaplugin = library('amdaplugin',
                       amdaplugin_sources,
                       amdaplugin_moc_files,
                       amdaplugin_rcc_plugin_files,
                       amdaplugin_moc_plugin_files,
                       cpp_args : ['-DAMDA_LIB','-DQT_PLUGIN'],
                       include_directories : [amdaplugin_inc],
                       dependencies : [sciqlop_core, sciqlop_gui],
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
                          link_with : [sciqlop_amdaplugin],
                          include_directories : [amdaplugin_inc],
                          cpp_args : ['-DAMDA_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/tests-resources"'],
                          dependencies : [sciqlop_core, sciqlop_gui, qt5test])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])], timeout: 3 * 60)
endforeach
