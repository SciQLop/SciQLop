
pybind11_dep = dependency('pybind11', required : true, fallback:['pybind11','pybind11_dep'])

python_providers_moc_headers = [
  'include/python_providers.h'
]

python_providers_sources = [
  'src/python_providers.cpp'
]

python_providers_inc = include_directories(['include'])


gen = generator(moc,
                output  : 'moc_@BASENAME@.cpp',
                arguments : ['@INPUT@',
                 '-DSCIQLOP_PLUGIN_JSON_FILE_PATH="'+meson.source_root()+'/plugins/python_providers/resources/python_providers.json"',
                 '-I', meson.current_source_dir()+'/include',
                 '-I', meson.current_source_dir()+'/../../core/include/',
                 '-o', '@OUTPUT@'])

python_providers_moc_files = gen.process(python_providers_moc_headers)

python_providers_prep_files = qt5.preprocess(qresources : 'resources/python_providers.qrc')

cpp_args = ['-DPYTHON_PROVIDERS_LIB','-DQT_PLUGIN']
if(get_option('default_library')=='static')
    cpp_args += ['-DQT_STATICPLUGIN']
endif

sciqlop_python_interpreter = library('python_interpreter',
                                     ['src/python_interpreter.cpp'],
                                     include_directories : [python_providers_inc],
                                     dependencies : [pybind11_dep, sciqlop_core],
                                     cpp_args : ['-DQT_NO_KEYWORDS'],
                                     install : true
                                     )


sciqlop_python_providers = library('pythonproviders',
                       python_providers_sources,
                       python_providers_moc_files,
                       python_providers_prep_files,
                       cpp_args : cpp_args,
                       include_directories : [python_providers_inc],
                       link_with : [sciqlop_python_interpreter],
                       dependencies : [sciqlop_core, sciqlop_gui, pybind11_dep],
                       install : true,
                       install_dir : join_paths(get_option('libdir'), 'SciQLop')
                       )
