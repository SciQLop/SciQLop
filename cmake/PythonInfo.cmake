
function(find_python_site_packages VAR)
    if(Python_SITELIB)
        set("${VAR}" "${Python_SITELIB}" PARENT_SCOPE)
        return()
    endif()

    execute_process(
            COMMAND "${PYTHON_EXECUTABLE}" -c "if True:
                from distutils import sysconfig
                print(sysconfig.get_python_lib(prefix=None, plat_specific=True))"
            OUTPUT_VARIABLE "${VAR}"
            OUTPUT_STRIP_TRAILING_WHITESPACE)
    set("${VAR}" "${${VAR}}" PARENT_SCOPE)
endfunction()

function(get_python_extension_suffix VAR)
    # from PySide2 CMakeLists.txt
    # Result of imp.get_suffixes() depends on the platform, but generally looks something like:
    # [('.cpython-34m-x86_64-linux-gnu.so', 'rb', 3), ('.cpython-34m.so', 'rb', 3),
    # ('.abi3.so', 'rb', 3), ('.so', 'rb', 3), ('.py', 'r', 1), ('.pyc', 'rb', 2)]
    # We pick the first most detailed one, strip of the file extension part.

    execute_process(
            COMMAND "${PYTHON_EXECUTABLE}" -c "if True:
               import sysconfig
               print(sysconfig.get_config_var('EXT_SUFFIX'))
               "
            OUTPUT_VARIABLE "${VAR}"
            OUTPUT_STRIP_TRAILING_WHITESPACE)
    set("${VAR}" "${${VAR}}" PARENT_SCOPE)
endfunction()
