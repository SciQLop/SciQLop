#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <pybind11/embed.h>
#include <pybind11/numpy.h>
#include <pybind11/chrono.h>
#include <pybind11/functional.h>

#include <string>
#include <sstream>

#include "pywrappers_common.h"
#include "CoreWrappers.h"

#include <Data/DataSeriesType.h>
#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>
#include <Data/Unit.h>
#include <Data/IDataProvider.h>

#include <Variable/VariableController.h>

#include <Time/TimeController.h>

#include <Network/Downloader.h>



namespace py = pybind11;
using namespace std::chrono;

PYBIND11_MODULE(pysciqlopcore,m){

    py::enum_<DataSeriesType>(m, "DataSeriesType")
            .value("SCALAR", DataSeriesType::SCALAR)
            .value("SPECTROGRAM", DataSeriesType::SPECTROGRAM)
            .value("UNKNOWN", DataSeriesType::UNKNOWN)
            .export_values();

    py::class_<Unit>(m, "Unit")
            .def_readwrite("name", &Unit::m_Name)
            .def_readwrite("time_unit", &Unit::m_TimeUnit)
            .def(py::self == py::self)
            .def(py::self != py::self)
            .def("__repr__",__repr__<Unit>);

    py::class_<Response>(m,"Response")
            .def("status_code", &Response::status_code);

    py::class_<Downloader>(m,"Downloader")
            .def_static("get", Downloader::get)
            .def_static("getAsync", Downloader::getAsync)
            .def_static("downloadFinished", Downloader::downloadFinished);

    py::class_<DataSeriesIteratorValue>(m,"DataSeriesIteratorValue")
            .def_property_readonly("x", &DataSeriesIteratorValue::x)
            .def("value", py::overload_cast<>(&DataSeriesIteratorValue::value, py::const_))
            .def("value", py::overload_cast<int>(&DataSeriesIteratorValue::value, py::const_));

    py::class_<IDataSeries, std::shared_ptr<IDataSeries>>(m, "IDataSeries")
            .def("nbPoints", &IDataSeries::nbPoints)
            .def_property_readonly("xAxisUnit", &IDataSeries::xAxisUnit)
            .def_property_readonly("yAxisUnit", &IDataSeries::yAxisUnit)
            .def_property_readonly("valuesUnit", &IDataSeries::valuesUnit)
            .def("__getitem__", [](IDataSeries& serie, int key) {
        return *(serie.begin()+key);
    }, py::is_operator())
            .def("__len__", &IDataSeries::nbPoints)
            .def("__iter__", [](IDataSeries& serie) {
        return py::make_iterator(serie.begin(), serie.end());
    }, py::keep_alive<0, 1>())
            .def("__repr__",__repr__<IDataSeries>);

    py::class_<ScalarSeries, std::shared_ptr<ScalarSeries>, IDataSeries>(m, "ScalarSeries")
            .def("nbPoints", &ScalarSeries::nbPoints);

    py::class_<VectorSeries, std::shared_ptr<VectorSeries>, IDataSeries>(m, "VectorSeries")
            .def("nbPoints", &VectorSeries::nbPoints);


    py::class_<IDataProvider, std::shared_ptr<IDataProvider>>(m, "IDataProvider");


    py::class_<Variable,std::shared_ptr<Variable>>(m, "Variable")
            .def(py::init<const QString&>())
            .def_property("name", &Variable::name, &Variable::setName)
            .def_property("range", &Variable::range, &Variable::setRange)
            .def_property("cacheRange", &Variable::cacheRange, &Variable::setCacheRange)
            .def_property_readonly("nbPoints", &Variable::nbPoints)
            .def_property_readonly("dataSeries", &Variable::dataSeries)
            .def("__len__", [](Variable& variable) {
        auto rng = variable.dataSeries()->xAxisRange(variable.range().m_TStart,variable.range().m_TEnd);
        return std::distance(rng.first,rng.second);
    })
            .def("__iter__", [](Variable& variable) {
        auto rng = variable.dataSeries()->xAxisRange(variable.range().m_TStart,variable.range().m_TEnd);
        return py::make_iterator(rng.first, rng.second);
    }, py::keep_alive<0, 1>())
            .def("__getitem__", [](Variable& variable, int key) {
        //insane and slow!
        auto rng = variable.dataSeries()->xAxisRange(variable.range().m_TStart,variable.range().m_TEnd);
        if(key<0)
            return *(rng.second+key);
        else
            return *(rng.first+key);
    })
            .def("__repr__",__repr__<Variable>);


    py::class_<DateTimeRange>(m,"SqpRange")
            .def("fromDateTime", &DateTimeRange::fromDateTime, py::return_value_policy::move)
            .def(py::init([](double start, double stop){return DateTimeRange{start, stop};}))
            .def(py::init([](system_clock::time_point start, system_clock::time_point stop)
    {
                     double start_ = 0.001 * duration_cast<milliseconds>(start.time_since_epoch()).count();
                     double stop_ = 0.001 * duration_cast<milliseconds>(stop.time_since_epoch()).count();
                     return DateTimeRange{start_, stop_};
                 }))
            .def_property_readonly("start", [](const DateTimeRange& range){
        return  system_clock::from_time_t(range.m_TStart);
    })
            .def_property_readonly("stop", [](const DateTimeRange& range){
        return  system_clock::from_time_t(range.m_TEnd);
    })
            .def("__repr__", __repr__<DateTimeRange>);

}
