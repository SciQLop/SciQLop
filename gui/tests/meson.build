
tests_inc = include_directories(['GUITestUtils'])

tests = [
    {
        'name':'simple_graph',
        'sources': ['simple_graph/main.cpp'],
        'deps': [sciqlop_gui, qt5test, TestUtils_dep]
    },
    {
        'name':'multiple_sync_graph',
        'sources': ['multiple_sync_graph/main.cpp'],
        'deps': [sciqlop_gui, qt5test, TestUtils_dep]
    }
]

foreach unit_test : tests
  test_moc_files = qt5.preprocess(moc_sources : unit_test['sources'])
  test_exe = executable(unit_test['name'],unit_test['sources'] , test_moc_files,
                          dependencies : unit_test['deps'],
                          include_directories: tests_inc,
						  cpp_args : ['-DCORE_TESTS_RESOURCES_DIR="'+meson.current_source_dir()+'/../tests-resources"']
						  )
  test('Test-' + unit_test['name'], test_exe, args: ['-teamcity', '-o', '@0@.teamcity.txt'.format(unit_test['name'])])
endforeach
