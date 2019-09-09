project('SciQLOP', 'cpp',default_options : ['cpp_std=c++17'], meson_version:'>=0.51.0')
add_global_arguments('-DSCIQLOP_VERSION="1.1.0"', language : 'cpp')

qt5 = import('qt5')
qt5core = dependency('qt5', modules : 'Core')
qt5widgets = dependency('qt5', modules : 'Widgets')
qt5gui = dependency('qt5', modules : 'Gui')
qt5svg = dependency('qt5', modules : 'Svg')
qt5xml = dependency('qt5', modules : 'Xml')
qt5network = dependency('qt5', modules : 'Network')
qt5printsupport = dependency('qt5', modules : 'PrintSupport')
qt5Concurrent = dependency('qt5', modules : 'Concurrent')
qt5test = dependency('qt5', modules : 'Test')

cpp_utils_dep = dependency('cpp_utils', fallback:['cpp_utils','cpp_utils_dep'])

moc = find_program('moc-qt5','moc')
rcc = find_program('rcc-qt5','rcc')

if build_machine.system()=='darwin'
  add_global_link_arguments('-headerpad_max_install_names', language : 'cpp')
  install_data('build_cfg/mac/sciqlopLOGO.icns', install_dir : 'Contents/Resources')
  install_data('build_cfg/mac/Info.plist', install_dir : 'Contents')
  meson.add_install_script('build_cfg/mac/install_script.sh')
elif host_machine.system()=='windows'
  meson.add_install_script('build_cfg/windows/install_script.sh')
elif host_machine.system()=='linux'
  install_data('app/resources/sciqlopLOGO.svg', install_dir : 'share/icons/hicolor/scalable/')
  install_data('app/resources/SciQLOP.desktop', install_dir : 'share/applications')
  install_data('app/resources/SciQLOP.appdata.xml', install_dir : 'share/metainfo')
endif

# Sets AMDA server that will be used during execution.
# Available values are:
# - "default": default AMDA server
# - "amdatest": AMDA test server
# - "hybrid": use both the default server and the test server (the server used is relative to each product, according to its "server" property in the JSON file)
# - "localhost": use local AMDA server
# Any other value will lead to the use of the default server
add_project_arguments('-DSCIQLOP_AMDA_SERVER="hybrid"', language : 'cpp')

subdir('core')
subdir('gui')
subdir('plugins')
subdir('app')

cppcheck = find_program('cppcheck', required : false)

if cppcheck.found()
  run_target('cppcheck',
              command : [cppcheck, '--enable=all',
              '--project=' + join_paths(meson.build_root(), 'compile_commands.json')]
              )
endif
