#include "python_providers.h"
#include <pybind11/embed.h>
namespace py = pybind11;

void PythonProviders::initialize()
{
    py::initialize_interpreter(false);
    py::print("Hello, World!");
    py::print("Hello, World!");
    py::print("Hello, World!");
    py::print("Hello, World!");
}

PythonProviders::~PythonProviders()
{
    py::finalize_interpreter();
}
