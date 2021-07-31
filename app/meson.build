
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

cpp_args = ['-DQT_STATICPLUGIN']


sciqlop_app_lib = library('sciqlop',
                       app_sources,
                       app_moc_files,
                       rc,
                       include_directories : [ app_inc],
                       cpp_args: cpp_args,
                       dependencies : [sciqlop_gui, sciqlop_core, demo_plugin_dep],
                       install : true
                       )

sciqlop_app_dep = declare_dependency(link_with : sciqlop_app_lib,
                                include_directories : app_inc,
                                dependencies : [sciqlop_gui, sciqlop_core])

                       
subdir('PySide2-bindings')
