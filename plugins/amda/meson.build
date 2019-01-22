
amdaplugin_moc_headers = [
  'include/AmdaPlugin.h',
  'include/AmdaProvider.h'
]

amdaplugin_sources = [
  'src/AmdaDefs.cpp',
  'src/AmdaParser.cpp',
  'src/AmdaPlugin.cpp',
  'src/AmdaProvider.cpp',
  'src/AmdaResultParser.cpp',
  'src/AmdaResultParserDefs.cpp',
  'src/AmdaResultParserHelper.cpp',
  'src/AmdaServer.cpp'
]

amdaplugin_ui_files = []
amdaplugin_resources_files = [
  'resources/amdaresources.qrc'
]

amdaplugin_inc = include_directories(['include'])

amdaplugin_prep_files = qt5.preprocess(moc_headers : amdaplugin_moc_headers,
                                             moc_extra_arguments: ['-DSCIQLOP_PLUGIN_JSON_FILE_PATH="'+
                                                                   meson.source_root()+
                                                                   '/plugins/amda/resources/amda.json"'],
                                             include_directories: [amdaplugin_inc, core_inc],
                                             qresources : amdaplugin_resources_files,
                                             ui_files : amdaplugin_ui_files)

cpp_args = ['-DAMDA_LIB','-DQT_PLUGIN']
message('======================='+get_option('default_library')+'==========================')
if(get_option('default_library') == 'static')
    message('building amda plugin as static lib')
    cpp_args += ['-DQT_STATICPLUGIN']
endif

sciqlop_amdaplugin = library('amdaplugin',
                       amdaplugin_sources,
                       amdaplugin_prep_files,
                       cpp_args : cpp_args,
                       include_directories : [amdaplugin_inc],
                       dependencies : [sciqlop_core, sciqlop_gui],
                       install : true,
                       install_dir : join_paths(get_option('libdir'), 'SciQLop')
                       )


tests = [
  [['tests/TestAmdaParser.cpp'],'test_amda_parser','AMDA parser test'],
  [['tests/TestAmdaResultParser.cpp'],'test_amda_result_parser','AMDA result parser test'],
  [['tests/TestAmdaAcquisition.cpp'],'test_amda_acquisition','AMDA Acquisition test'],
  [['tests/TestAmdaFuzzing.cpp'],'test_amda_fuzzing','AMDA fuzzing test']
]

tests_sources = [
  'tests/FuzzingDefs.h',
  'tests/FuzzingDefs.cpp',
  'tests/FuzzingOperations.h',
  'tests/FuzzingOperations.cpp',
  'tests/FuzzingUtils.h',
  'tests/FuzzingUtils.cpp',
  'tests/FuzzingValidators.h',
  'tests/FuzzingValidators.cpp'
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test[0])
  test_exe = executable(unit_test[1],unit_test[0] , test_moc_files,
                          link_with : [sciqlop_amdaplugin],
                          include_directories : [amdaplugin_inc],
                          cpp_args : ['-DAMDA_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/tests-resources"'],
						  sources : [tests_sources],
                          dependencies : [sciqlop_core, sciqlop_gui, qt5test])
  test(unit_test[2], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test[1])], timeout: 3 * 60)
endforeach
