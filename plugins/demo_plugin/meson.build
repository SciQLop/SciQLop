demoplugin_moc_headers = [
  'DemoPlugin.hpp'
]

demoplugin_sources = [
  'DemoPlugin.cpp'
]


demoplugin_moc_files = qt5.preprocess(
                                     moc_headers: demoplugin_moc_headers,
                                     dependencies: sciqlop_core,
                                     include_directories: core_inc,
                                     moc_extra_arguments : ['-DQT_PLUGIN', '-DQT_STATICPLUGIN']
                                     )

demo_plugin = static_library('demo_plugin',
                       'DemoPlugin.cpp',
                       demoplugin_moc_files,
                       extra_files: 'DemoPlugin.hpp',
                       dependencies : [sciqlop_core],
                       cpp_args : ['-DQT_PLUGIN', '-DQT_STATICPLUGIN']
                       )

demo_plugin_dep = declare_dependency(link_with: demo_plugin, include_directories: '.')
