
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
