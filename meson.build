project('SciQLOP', 'cpp',default_options : ['cpp_std=c++14'])

qt5 = import('qt5')
qt5core = dependency('qt5', modules : 'Core')
qt5widgets = dependency('qt5', modules : 'Widgets')
qt5gui = dependency('qt5', modules : 'Gui')
qt5svg = dependency('qt5', modules : 'Svg')
qt5xml = dependency('qt5', modules : 'Xml')
qt5network = dependency('qt5', modules : 'Network')
qt5printsupport = dependency('qt5', modules : 'PrintSupport')
qt5test = dependency('qt5', modules : 'Test')

moc = find_program('moc','moc-qt5')

subdir('core')
subdir('gui')
subdir('app')
subdir('plugins')

if build_machine.system()=='darwin'
  install_data('build_cfg/mac/sciqlopLOGO.icns', install_dir : 'Contents/Resources')
  install_data('build_cfg/mac/Info.plist', install_dir : 'Contents')
  meson.add_install_script('build_cfg/mac/install_script.sh')
elif host_machine.system()=='windows'
  meson.add_install_script('build_cfg/windows/install_script.sh')
endif

cppcheck = find_program('cppcheck', required : false)

if cppcheck.found()
  run_target('cppcheck',
              command : [cppcheck, '--enable=all',
              '--project=' + join_paths(meson.build_root(), 'compile_commands.json')],
              build_by_default : true
              )
endif
