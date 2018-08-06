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

//#include <QDate>
//#include <QTime>
//#include <QUuid>
//#include <QString>
#include <QFile>

#include <pywrappers_common.h>
#include <CoreWrappers.h>

#include "PyTestAmdaWrapper.h"


using namespace std::chrono;




PYBIND11_MODULE(pytestamda, m){

    int argc = 0;
    char ** argv=nullptr;
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");
    static SqpApplication app(argc, argv);

    auto qtmod = py::module::import("sciqlopqt");
    auto sciqlopmod = py::module::import("pysciqlopcore");

    m.doc() = "hello";

    py::class_<VariableController>(m, "VariableController")
            .def_static("createVariable",[](const QString &name,
                        std::shared_ptr<IDataProvider> provider, const DateTimeRange& range){
        return sqpApp->variableController().createVariable(name, {{"dataType", "vector"}, {"xml:id", "c1_b"}}, provider, range);
    })
            .def_static("hasPendingDownloads",
                        [](){return sqpApp->variableController().hasPendingDownloads();}
                        )
            .def_static("addSynchronizationGroup",
                        [](QUuid uuid){sqpApp->variableController().onAddSynchronizationGroupId(uuid);}
                        )
            .def_static("removeSynchronizationGroup",
                [](QUuid uuid){sqpApp->variableController().onRemoveSynchronizationGroupId(uuid);}
                )
            .def_static("synchronizeVar",
                [](std::shared_ptr<Variable> variable, QUuid uuid){sqpApp->variableController().onAddSynchronized(variable, uuid);}
                )
            .def_static("deSynchronizeVar",
                [](std::shared_ptr<Variable> variable, QUuid uuid){sqpApp->variableController().desynchronize(variable, uuid);}
                )
            .def_static("deleteVariable",
                        [](std::shared_ptr<Variable> variable){
        sqpApp->variableController().deleteVariable(variable);}
                        )
            .def_static("update_range",[](std::shared_ptr<Variable> variable, const DateTimeRange &range, bool synchronise){
        sqpApp->variableController().onRequestDataLoading({variable}, range, synchronise);
    })
            .def_static("wait_for_downloads",[](){
        while (sqpApp->variableController().hasPendingDownloads()) {
            usleep(100);
        }
    });

    py::class_<TimeController>(m,"TimeController")
            .def_static("setTime", [](DateTimeRange range){sqpApp->timeController().setDateTimeRange(range);});


    auto amda_provider = std::make_shared<AmdaProvider>();
    m.def("amda_provider",[amda_provider](){return amda_provider;}, py::return_value_policy::copy);

    py::class_<AmdaProvider, std::shared_ptr<AmdaProvider>, IDataProvider>(m, "AmdaProvider");

    py::class_<AmdaResultParser>(m, "AmdaResultParser")
            .def_static("readTxt", AmdaResultParser::readTxt)
            .def("readScalarTxt", [](const QString& path){
        return std::dynamic_pointer_cast<ScalarSeries>(AmdaResultParser::readTxt(path, DataSeriesType::SCALAR));
    }, py::return_value_policy::copy);


}

