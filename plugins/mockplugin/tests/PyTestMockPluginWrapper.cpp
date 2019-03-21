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
#include <memory>
#include <sstream>
#include <string>

#include <pybind11/chrono.h>
#include <pybind11/embed.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/pybind11.h>

#include <Common/DateUtils.h>
#include <Data/DataSeriesType.h>
#include <Data/DateTimeRange.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/VariableController2.h>

#include <CosinusProvider.h>
#include <MockPlugin.h>

#include <QFile>

#include <CoreWrappers.h>
#include <pywrappers_common.h>


using namespace std::chrono;
namespace py = pybind11;


PYBIND11_MODULE(pytestmockplugin, m)
{

    int argc = 0;
    char** argv = nullptr;
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");
    static SqpApplication app(argc, argv);

    auto qtmod = py::module::import("sciqlopqt");
    auto sciqlopmod = py::module::import("pysciqlopcore");

    m.doc() = "";

    py::class_<VariableController2>(m, "VariableController2")
        .def_static("createVariable",
            [](const QString& name, std::shared_ptr<IDataProvider> provider,
                const DateTimeRange& range) {
                return sqpApp->variableController().createVariable(name,
                    { { "cosinusType", "spectrogram" }, { "cosinusFrequency", "0.1" } }, provider,
                    range);
            });

    py::class_<TimeController>(m, "TimeController").def_static("setTime", [](DateTimeRange range) {
        sqpApp->timeController().setDateTimeRange(range);
    });

    auto mock_provider = std::make_shared<CosinusProvider>();
    m.def("mock_provider", [mock_provider]() { return mock_provider; },
        py::return_value_policy::copy);

    py::class_<CosinusProvider, std::shared_ptr<CosinusProvider>, IDataProvider>(
        m, "CosinusProvider");
}
