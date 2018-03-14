/*------------------------------------------------------------------------------
--  This file is a part of the SciQLOP Software
--  Copyright (C) 2018, Plasma Physics Laboratory - CNRS
--
--  This program is free software; you can redistribute it and/or modify
--  it under the terms of the GNU General Public License as published by
--  the Free Software Foundation; either version 2 of the License, or
--  (at your option) any later version.
--
--  This program is distributed in the hope that it will be useful,
--  but WITHOUT ANY WARRANTY; without even the implied warranty of
--  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
--  GNU General Public License for more details.
--
--  You should have received a copy of the GNU General Public License
--  along with this program; if not, write to the Free Software
--  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
-------------------------------------------------------------------------------*/
/*--                  Author : Alexis Jeandet
--                     Mail : alexis.jeandet@member.fsf.org
----------------------------------------------------------------------------*/
#include <string>
#include <sstream>
#include <memory>

#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <pybind11/embed.h>
#include <pybind11/numpy.h>
#include <pybind11/chrono.h>

#include <SqpApplication.h>
#include <Variable/VariableController.h>
#include <Time/TimeController.h>
#include <Data/SqpRange.h>
#include <Data/DataSeriesType.h>
#include <Common/DateUtils.h>
#include <Variable/Variable.h>
#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>

#include <AmdaProvider.h>
#include <AmdaResultParser.h>

#include <QDate>
#include <QTime>
#include <QUuid>
#include <QString>
#include <QFile>

using namespace std::chrono;
namespace py = pybind11;

std::ostream &operator <<(std::ostream& os, const Unit& u)
{
    os << "=========================" << std::endl
       << "Unit:" << std::endl
       << " Name: " << u.m_Name.toStdString() << std::endl
       << " Is_TimeUnit: " << u.m_TimeUnit << std::endl;
    return os;
}

std::ostream &operator <<(std::ostream& os, const IDataSeries& ds)
{
    os << "=========================" << std::endl
       << "DataSerie:" << std::endl
       << " Number of points:" << ds.nbPoints() << std::endl
       << " X Axis Unit:" << std::endl << ds.xAxisUnit() << std::endl
       << " Y Axis Unit:" << std::endl << ds.yAxisUnit()<< std::endl
       << " Values Axis Unit:" << std::endl << ds.valuesUnit()<< std::endl;
    return os;
}

std::ostream &operator <<(std::ostream& os, const SqpRange& range)
{
    os << "=========================" << std::endl
       << "SqpRange:" << std::endl
       << " Start date: " << DateUtils::dateTime(range.m_TStart).toString().toStdString() << std::endl
       << " Stop date: "  << DateUtils::dateTime(range.m_TEnd).toString().toStdString() << std::endl;
    return os;
}

std::ostream &operator <<(std::ostream& os, const Variable& variable)
{
    os << "=========================" << std::endl
       << "Variable:" << std::endl
       << " Name: " << variable.name().toStdString() << std::endl
       << " range: " << std::endl << variable.range() << std::endl
       << " cache range: " << std::endl << variable.cacheRange() << std::endl;
    return os;
}

template <typename T>
std::string __repr__(const T& obj)
{
    std::stringstream sstr;
    sstr << obj;
    return sstr.str();
}




PYBIND11_MODULE(pytestamda, m){
    int argc = 0;
    char ** argv=nullptr;
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");
    static SqpApplication app(argc, argv);

    m.doc() = "hello";

    auto amda_provider = std::make_shared<AmdaProvider>();
    m.def("amda_provider",[amda_provider](){return amda_provider;}, py::return_value_policy::copy);

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

    py::class_<QString>(m, "QString")
            .def(py::init([](const std::string& value){return QString::fromStdString(value);}))
            .def("__repr__", &QString::toStdString);

    py::class_<VariableController>(m, "VariableController")
            .def_static("createVariable",[](const QString &name,
                        std::shared_ptr<IDataProvider> provider){
        return sqpApp->variableController().createVariable(name, {{"dataType", "vector"}, {"xml:id", "c1_b"}}, provider);
    })
            .def_static("hasPendingDownloads",
                        [](){return sqpApp->variableController().hasPendingDownloads();}
                        );

    py::class_<TimeController>(m,"TimeController")
            .def_static("setTime", [](SqpRange range){sqpApp->timeController().onTimeToUpdate(range);});

    py::class_<IDataProvider, std::shared_ptr<IDataProvider>>(m, "IDataProvider");

    py::class_<AmdaProvider, std::shared_ptr<AmdaProvider>, IDataProvider>(m, "AmdaProvider");

    py::class_<AmdaResultParser>(m, "AmdaResultParser")
            .def_static("readTxt", AmdaResultParser::readTxt)
            .def("readScalarTxt", [](const QString& path){
        return std::dynamic_pointer_cast<ScalarSeries>(AmdaResultParser::readTxt(path, DataSeriesType::SCALAR));
    }, py::return_value_policy::copy);

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

    py::implicitly_convertible<std::string, QString>();


    py::class_<SqpRange>(m,"SqpRange")
            .def("fromDateTime", &SqpRange::fromDateTime, py::return_value_policy::move)
            .def(py::init([](double start, double stop){return SqpRange{start, stop};}))
            .def(py::init([](system_clock::time_point start, system_clock::time_point stop)
    {
                     double start_ = 0.001 * duration_cast<milliseconds>(start.time_since_epoch()).count();
                     double stop_ = 0.001 * duration_cast<milliseconds>(stop.time_since_epoch()).count();
                     return SqpRange{start_, stop_};
                 }))
            .def_property_readonly("start", [](const SqpRange& range){
        return  system_clock::from_time_t(range.m_TStart);
    })
            .def_property_readonly("stop", [](const SqpRange& range){
        return  system_clock::from_time_t(range.m_TEnd);
    })
            .def("__repr__", __repr__<SqpRange>);

    py::class_<QUuid>(m,"QUuid");

    py::class_<QDate>(m,"QDate")
            .def(py::init<int,int,int>());

    py::class_<QTime>(m,"QTime")
            .def(py::init<int,int,int>());

}


int pytestamda_test(const char* testScriptPath )
{
    py::scoped_interpreter guard{};
    py::globals()["__file__"] = py::str(testScriptPath);
    py::eval_file(testScriptPath);
    return 0;
}

