#include <QString>
#include <QUuid>
#include <QDate>
#include <QTime>
#include <string>
#include <sstream>
#include "pywrappers_common.h"
#include <pybind11/pybind11.h>
#include "QtWrappers.h"

namespace py = pybind11;



PYBIND11_MODULE(sciqlopqt,m){
    py::class_<QString>(m, "QString")
            .def(py::init([](const std::string& value){return QString::fromStdString(value);}))
            .def("__repr__", __repr__<QString>);

    py::class_<QUuid>(m,"QUuid")
            .def(py::init([](){return QUuid::createUuid();}))
            .def("__repr__",__repr__<QUuid>);

    py::class_<QDate>(m,"QDate")
            .def(py::init<int,int,int>());

    py::class_<QTime>(m,"QTime")
            .def(py::init<int,int,int>());


    py::implicitly_convertible<std::string, QString>();
}

