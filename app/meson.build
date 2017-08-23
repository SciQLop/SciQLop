
app_moc_headers = [
  'include/MainWindow.h'
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
  'src/MainWindow.cpp'
]

app_inc = include_directories(['include'])

if host_machine.system()=='windows' or build_machine.system()=='windows'
  winmod = import('windows')
  rc = winmod.compile_resources('resources/qlopapp.rc')
else
  rc = []
endif

sciqlop_app = executable('sciqlop',
                       app_sources,
                       app_moc_files,
                       rc,
                       link_with : [sciqlop_core, sciqlop_gui],
                       include_directories : [gui_inc, core_inc, app_inc],
                       dependencies : [qt5core, qt5printsupport, qt5gui, qt5widgets, qt5network],
                       install : true
                       )

