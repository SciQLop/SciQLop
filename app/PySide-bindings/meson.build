if qt_sdk == 'qt5'
    qmake_possible_names = ['qmake','qmake-qt5']
    pyside_version = '2'
elif qt_sdk == 'qt6'
    qmake_possible_names = ['qmake','qmake6']
    pyside_version = '6'
else
    error('Only Qt5 or Qt6 are supported')
endif


shiboken = find_program('shiboken@0@'.format(pyside_version))
qmake = find_program(qmake_possible_names)

pymod = import('python')
python3 = pymod.find_installation('python3', modules:['PySide@0@'.format(pyside_version),
                                                      'shiboken@0@'.format(pyside_version),
                                                      'shiboken@0@_generator'.format(pyside_version),
                                                      'numpy'])
python3_dep = python3.dependency(embed:true)
numpy_inc = run_command(python3, '-c', 'import numpy;print(numpy.get_include())').stdout().strip('\n')

qt_modules = ['QtCore','QtGui','QtWidgets']

qt_headers_path = run_command(qmake, '-query', 'QT_INSTALL_HEADERS').stdout().strip('\n')
generated_srcs  = run_command(python3, 'src_list.py', 'meson').stdout().split(';')

modules_arg = '--modules=@0@'.format(','.join(qt_modules))

shiboken_build_flags = run_command(python3, 'shiboken-helper.py', '--qmake', qmake.full_path(), '--pyside_version', pyside_version, '--includes', modules_arg).stdout().strip('\n').split(' ')
shiboken_link_flags  = run_command(python3, 'shiboken-helper.py', '--qmake', qmake.full_path(), '--pyside_version', pyside_version, '--libs', modules_arg).stdout().strip('\n').split(' ')
shiboken_typesystem  = run_command(python3, 'shiboken-helper.py', '--qmake', qmake.full_path(), '--pyside_version', pyside_version, '--typesystem').stdout().strip('\n')


sciqlop_bindings_incs = shiboken_build_flags + [
    '-I'+meson.current_source_dir()+'/../../gui/include',
    '-I'+meson.current_source_dir()+'/../../core/include',
    '-I'+meson.current_source_dir()+'/../../subprojects/TimeSeries/include',
    '-I'+meson.current_source_dir()+'/../../subprojects/cpp_utils/include',
    '-I'+python3.get_path('include'),
    '-I'+qt_headers_path,
    '-I'+numpy_inc
    ]

foreach mod:qt_modules
    sciqlop_bindings_incs += ['-I'+qt_headers_path+'/'+mod]
endforeach


sciqlop_bindings_src = files('bindings.h', 'PyDataProvider.h', 'numpy_wrappers.h', 'numpy_wrappers.cpp')

subdir('SciQLopBindings')
subdir('plugins')

shiboken_dep = declare_dependency(compile_args: shiboken_build_flags, link_args: shiboken_link_flags)

sciqlop_bindings = python3.extension_module('SciQLopBindings', sciqlop_bindings_src, shiboken_generator_out,
        dependencies : [sciqlop_app_dep, python3_dep, shiboken_dep, cpp_utils_dep],
        include_directories : numpy_inc
)


#configure_file(input:'main.py.in', output:'main.py', copy:true)


main_py = custom_target(
    'main.py',
    build_by_default: true,
    output : 'main.py',
    input : 'main.py.in',
    command : [python3, files('gen_main.py'), '--qt_version', qt_sdk, '--input', '@INPUT@', '--output', '@OUTPUT@']
)

executable('sciqlop', 'main.cpp', dependencies :python3_dep , extra_files:['gen_main.py'])

summary(
    {
        'Pyside Version': pyside_version,
        'shiboken path': shiboken.full_path(),
        'shiboken_build_flags':shiboken_build_flags,
        'shiboken_link_flags':shiboken_link_flags,
        'shiboken_typesystem':shiboken_typesystem
    },
    section:'Pyside'
)
