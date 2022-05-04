project(
  'SciQLOP',
  'cpp',
  default_options : 'cpp_std=c++17',
  meson_version : '>=0.61.0',
  version : '1.1.0',
  license : 'GPL3'
)
add_global_arguments('-DSCIQLOP_VERSION="@0@"'.format(meson.project_version()), language : 'cpp')

qt_sdk=get_option('qt_version')
if qt_sdk=='auto'
    qt_version=run_command(find_program('qmake'), '-query', 'QT_VERSION').stdout()
    if qt_version.startswith('5.')
        qt_sdk='qt5'
    elif qt_version.startswith('6.')
        qt_sdk='qt6'
    endif
endif


qtmod = import(qt_sdk)

qt_core = dependency(qt_sdk, modules : 'Core', method:'qmake')
qt_widgets = dependency(qt_sdk, modules : 'Widgets')
qt_gui = dependency(qt_sdk, modules : 'Gui')
qt_svg = dependency(qt_sdk, modules : 'Svg')
qt_xml = dependency(qt_sdk, modules : 'Xml')
qt_network = dependency(qt_sdk, modules : 'Network')
qt_printsupport = dependency(qt_sdk, modules : 'PrintSupport')
qt_Concurrent = dependency(qt_sdk, modules : 'Concurrent')
qt_test = dependency(qt_sdk, modules : 'Test')

cpp_utils_dep = dependency('cpp_utils', fallback:['cpp_utils','cpp_utils_dep'])

#moc = find_program('moc-qt6','moc')
#rcc = find_program('rcc-qt6','rcc')

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
