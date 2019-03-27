#include "python_interpreter.h"
#include <Data/DateTimeRange.h>
#include <TimeSeries.h>
#include <functional>
#include <iostream>
#include <pybind11/embed.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

namespace py = pybind11;


PYBIND11_EMBEDDED_MODULE(PythonProviders, m) {}
static pybind11::gil_scoped_release* _rel = nullptr;

PythonInterpreter::PythonInterpreter()
{
    py::initialize_interpreter(false);
}

void PythonInterpreter::add_register_callback(std::function<void(const std::vector<std::string>&,
        std::function<std::shared_ptr<TimeSeries::ITimeSerie>(std::string&, double, double)>)>
        callback)
{
    py::module PythonProviders = py::module::import("PythonProviders");
    PythonProviders.attr("register_product") = callback;
}

PythonInterpreter::~PythonInterpreter()
{
    if (_rel)
        delete _rel;
    py::finalize_interpreter();
}

void PythonInterpreter::eval(const std::string& file)
{
    try
    {
        py::eval_file(file);
    }
    catch (py::error_already_set const& pythonErr)
    {
        std::cout << pythonErr.what();
    }
    _rel = new py::gil_scoped_release();
}
