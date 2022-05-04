
shiboken_generator_out = custom_target('sciqlop_bindings',
                                build_by_default:true,
                                output:generated_srcs,
                                input:'../bindings.xml',
                                depend_files:sciqlop_bindings_src,
                                command:[shiboken, meson.current_source_dir()+'/../bindings.h',meson.current_source_dir()+'/../bindings.xml','--generator-set=shiboken',
                                '--enable-parent-ctor-heuristic',
                                '--enable-return-value-heuristic',
                                '--use-isnull-as-nb_nonzero',
                                '--avoid-protected-hack',
                                '--enable-pyside-extensions',
                                '-std=c++17',
                                '--typesystem-paths='+shiboken_typesystem,
                                sciqlop_bindings_incs,
                                '--output-directory='+meson.current_build_dir()+'/../']
                                )
