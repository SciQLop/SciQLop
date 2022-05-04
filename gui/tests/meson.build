
tests_inc = include_directories(['GUITestUtils'])

tests = [
    {
        'name':'simple_graph',
        'sources': ['simple_graph/main.cpp'],
        'deps': [sciqlop_gui, qt_test, TestUtils_dep]
    },
    {
        'name':'multiple_sync_graph',
        'sources': ['multiple_sync_graph/main.cpp'],
        'deps': [sciqlop_gui, qt_test, TestUtils_dep]
    }
]

foreach unit_test : tests
  test_moc_files = qtmod.preprocess(moc_sources : unit_test['sources'])
  test_exe = executable(unit_test['name'],unit_test['sources'] , test_moc_files,
                          dependencies : unit_test['deps'],
                          include_directories: tests_inc,
						  cpp_args : ['-DCORE_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/../tests-resources"']
						  )
  if get_option('teamcity')
    test_exe_args = ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test['name'])]
  else
    test_exe_args = []
  endif
  test('Test-' + unit_test['name'], test_exe, args: test_exe_args)
endforeach
