shiboken2 = find_program('shiboken2')
qmake = find_program('qmake-qt5','qmake')

pymod = import('python')
python3 = pymod.find_installation('python3', modules:['PySide2','shiboken2', 'shiboken2_generator'])

qt5_modules = ['QtCore','QtGui','QtWidgets']

qt_headers_path = run_command(qmake, '-query', 'QT_INSTALL_HEADERS').stdout().strip('\n')
generated_srcs  = run_command(python3, 'src_list.py', 'meson').stdout().split(';')

modules_arg = '--modules=@0@'.format(','.join(qt5_modules))

shiboken2_build_flags = run_command(python3, 'shiboken-helper.py', '--includes', modules_arg).stdout().strip('\n').split(' ')
shiboken2_link_flags  = run_command(python3, 'shiboken-helper.py', '--libs', modules_arg).stdout().strip('\n').split(' ')
shiboken2_typesystem  = run_command(python3, 'shiboken-helper.py', '--typesystem').stdout().strip('\n')

sciqlop_bindings_incs = shiboken2_build_flags + [
    '-I'+meson.current_source_dir()+'/../../gui/include',
    '-I'+meson.current_source_dir()+'/../../core/include',
    '-I'+meson.current_source_dir()+'/../../subprojects/TimeSeries/include',
    '-I'+meson.current_source_dir()+'/../../subprojects/cpp_utils/include',
    '-I'+python3.get_path('include'),
    '-I'+qt_headers_path
    ]

foreach mod:qt5_modules
    sciqlop_bindings_incs += ['-I'+qt_headers_path+'/'+mod]
endforeach


sciqlop_bindings_src = files('bindings.h', 'PyDataProvider.h', 'numpy_wrappers.h', 'numpy_wrappers.cpp')

subdir('SciQLopBindings')
subdir('plugins')

shiboken_dep = declare_dependency(compile_args: shiboken2_build_flags, link_args: shiboken2_link_flags)

sciqlop_bindings = python3.extension_module('SciQLopBindings',sciqlop_bindings_src,shiboken2_generator_out,
        dependencies : [sciqlop_app_dep, python3.dependency(), shiboken_dep, cpp_utils_dep],
)


configure_file(input:'main.py', output:'main.py', copy:true)

executable('sciqlop', 'main.cpp', dependencies :python3.dependency())
