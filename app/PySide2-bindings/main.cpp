#include <fstream>
#include <iostream>
#define PY_SSIZE_T_CLEAN
#define Py_DEBUG
#include <Python.h>

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
