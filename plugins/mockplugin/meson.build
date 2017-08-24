
mockplugin_moc_headers = [
  'include/MockPlugin.h'
]

mockplugin_sources = [
  'src/CosinusProvider.cpp',
  'src/MockPlugin.cpp'
]

mockplugin_inc = include_directories(['include', '../../plugin/include'])


gen = generator(moc,
                output  : 'moc_@BASENAME@.cpp',
                arguments : ['@INPUT@',
                 '-DPLUGIN_JSON_FILE_PATH="'+meson.source_root()+'/plugins/mockplugin/resources/mockplugin.json"',
                 '-I', meson.current_source_dir()+'/include',
                 '-I', meson.current_source_dir()+'/../../plugin/include',
                 '-o', '@OUTPUT@'])

mockplugin_moc_files = gen.process(mockplugin_moc_headers)

sciqlop_mockplugin = library('mockplugin',
                       mockplugin_sources,
                       mockplugin_moc_files,
                       cpp_args : '-DMOCKPLUGIN_LIB',
                       link_with : [sciqlop_core, sciqlop_gui],
                       include_directories : [mockplugin_inc, core_inc, gui_inc],
                       dependencies : [qt5core, qt5gui, qt5widgets, qt5network],
                       install : true
                       )

