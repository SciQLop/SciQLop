#include "python_providers.h"
#include <pybind11/embed.h>
namespace py = pybind11;

void PythonProviders::initialize()
{
    py::scoped_interpreter guard {};
    py::print("Hello, World!");
}
