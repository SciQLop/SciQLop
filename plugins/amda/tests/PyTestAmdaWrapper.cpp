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

#include <SqpApplication.h>
#include <Variable/VariableController.h>
#include <Time/TimeController.h>
#include <Data/SqpRange.h>
#include <Data/DataSeriesType.h>
#include <Common/DateUtils.h>
#include <Variable/Variable.h>
#include <Data/ScalarSeries.h>

#include <AmdaProvider.h>
#include <AmdaResultParser.h>

#include <QDate>
#include <QTime>
#include <QUuid>
#include <QString>
#include <QFile>

namespace py = pybind11;

std::ostream &operator <<(std::ostream& os, const Unit& u)
{
    os << "=========================" << std::endl
       << "Unit:" << std::endl
       << "Name:" << std::endl << u.m_Name.toStdString() << std::endl
       << "Is_TimeUnit: " << u.m_TimeUnit << std::endl;
    return os;
}

std::ostream &operator <<(std::ostream& os, const IDataSeries& ds)
{
    os << "=========================" << std::endl
       << "DataSerie:" << std::endl
       << "Number of points:" << ds.nbPoints() << std::endl
       << "X Axis Unit:" << std::endl << ds.xAxisUnit() << std::endl
       << "Y Axis Unit:" << std::endl << ds.yAxisUnit()<< std::endl
       << "Values Axis Unit:" << std::endl << ds.valuesUnit()<< std::endl;
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
    m.doc() = "hello";

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

    py::class_<IDataSeries, std::shared_ptr<IDataSeries>>(m, "IDataSeries")
            .def("nbPoints", &IDataSeries::nbPoints)
            .def_property_readonly("xAxisUnit", &IDataSeries::xAxisUnit)
            .def_property_readonly("yAxisUnit", &IDataSeries::yAxisUnit)
            .def_property_readonly("valuesUnit", &IDataSeries::valuesUnit)
            .def("__repr__",__repr__<IDataSeries>);



    py::class_<ScalarSeries, std::shared_ptr<ScalarSeries>, IDataSeries>(m, "ScalarSeries")
            .def("nbPoints", &ScalarSeries::nbPoints);

    py::class_<QString>(m, "QString")
            .def(py::init([](const std::string& value){return QString::fromStdString(value);}))
            .def("__repr__", &QString::toStdString);

    py::class_<VariableController>(m, "VariableController");

    py::class_<AmdaProvider>(m, "AmdaProvider");

    py::class_<AmdaResultParser>(m, "AmdaResultParser")
            .def_static("readTxt", AmdaResultParser::readTxt)
            .def("readScalarTxt", [](const QString& path){
        return std::dynamic_pointer_cast<ScalarSeries>(AmdaResultParser::readTxt(path, DataSeriesType::SCALAR));
    }, py::return_value_policy::copy);

    py::class_<Variable>(m, "Variable")
            .def(py::init<const QString&>())
            .def_property("name", &Variable::name, &Variable::setName)
            .def_property("range", &Variable::range, &Variable::setRange)
            .def_property("cacheRange", &Variable::cacheRange, &Variable::setCacheRange);

    py::implicitly_convertible<std::string, QString>();

    py::class_<TimeController>(m,"TimeController");

    py::class_<SqpRange>(m,"SqpRange")
            .def("fromDateTime", &SqpRange::fromDateTime, py::return_value_policy::move)
            .def(py::init([](double start, double stop){return SqpRange{start, stop};}))
            .def("__repr__", [](const SqpRange& range){
        QString repr = QString("SqpRange:\n Start date: %1\n Stop date: %2")
                .arg(DateUtils::dateTime(range.m_TStart).toString())
                .arg(DateUtils::dateTime(range.m_TEnd).toString());
        return repr.toStdString();
    });

    py::class_<QUuid>(m,"QUuid");

    py::class_<QDate>(m,"QDate")
            .def(py::init<int,int,int>());

    py::class_<QTime>(m,"QTime")
            .def(py::init<int,int,int>());

}


int pytestamda_test(int argc, char** argv, const char* testScriptPath )
{
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");
    SqpApplication app(argc, argv);
    py::scoped_interpreter guard{};

    py::globals()["__file__"] = py::str(testScriptPath);
    py::eval_file(testScriptPath);
    return 0;
}

