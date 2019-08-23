#include <fstream>
#include <iostream>
#define PY_SSIZE_T_CLEAN
#define Py_DEBUG
#include <Python.h>

wchar_t** decode_argv(int argc, char** argv)
{
    wchar_t** _argv = static_cast<wchar_t**>(PyMem_Malloc(sizeof(wchar_t*) * argc));
    for (int i = 0; i < argc; i++)
    {
        wchar_t* arg = Py_DecodeLocale(argv[i], NULL);
        _argv[i] = arg;
    }
    return _argv;
}

int main(int argc, char** argv)
{
    wchar_t* program = Py_DecodeLocale(argv[0], NULL);
    if (program == NULL)
    {
        fprintf(stderr, "Fatal error: cannot decode argv[0]\n");
        exit(1);
    }

    Py_SetProgramName(program); /* optional but recommended */
    Py_Initialize();
    PySys_SetArgv(argc, decode_argv(argc, argv));
    std::ifstream t(argv[1]);
    std::string str((std::istreambuf_iterator<char>(t)), std::istreambuf_iterator<char>());
    PyRun_SimpleString(str.data());
    if (Py_FinalizeEx() < 0)
    {
        exit(120);
    }
    PyMem_RawFree(program);
    return 0;
}
