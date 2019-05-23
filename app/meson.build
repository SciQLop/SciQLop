
app_moc_headers = [
  'include/MainWindow.h',
  'include/toolbar.h'
]

app_ui_files = [
  'ui/MainWindow.ui'
]

app_qresources = ['resources/qlopapp.qrc']

app_moc_files = qt5.preprocess(moc_headers : app_moc_headers,
                               ui_files : app_ui_files,
                               qresources : app_qresources)

app_sources = [
  'src/Main.cpp',
  'src/MainWindow.cpp',
  'src/toolbar.cpp'
]

app_inc = include_directories(['include'])

if host_machine.system()=='windows' or build_machine.system()=='windows'
  winmod = import('windows')
  rc = winmod.compile_resources('resources/qlopapp.rc')
else
  rc = []
endif

app_libs = []
cpp_args = []
if 'static' == get_option('default_library')
  app_libs = [sciqlop_python_providers]
  cpp_args += ['-DQT_STATICPLUGIN']
endif

sciqlop_app = executable('sciqlop',
                       app_sources,
                       app_moc_files,
                       rc,
                       include_directories : [ app_inc],
                       link_with: app_libs,
                       cpp_args: cpp_args,
                       dependencies : [sciqlop_gui, sciqlop_core],
                       install : true
                       )
