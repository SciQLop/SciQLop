#include "Visualization/GraphPlottablesFactory.h"
#include "Visualization/qcustomplot.h"

#include <Data/ScalarSeries.h>

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_GraphPlottablesFactory, "GraphPlottablesFactory")

namespace {


QCPAbstractPlottable *createScalarSeriesComponent(ScalarSeries &scalarSeries, QCustomPlot &plot)
{
    auto component = plot.addGraph();

    if (component) {
        // Graph data
        component->setData(scalarSeries.xAxisData()->data(), scalarSeries.valuesData()->data(),
                           true);

        // Display all data
        component->rescaleAxes();

        plot.replot();
    }
    else {
        qCDebug(LOG_GraphPlottablesFactory())
            << QObject::tr("Can't create graph for the scalar series");
    }

    return component;
}

} // namespace

QVector<QCPAbstractPlottable *> GraphPlottablesFactory::create(const Variable *variable,
                                                               QCustomPlot &plot) noexcept
{
    auto result = QVector<QCPAbstractPlottable *>{};

    if (variable) {
        // Gets the data series of the variable to call the creation of the right components
        // according to its type
        if (auto scalarSeries = dynamic_cast<ScalarSeries *>(variable->dataSeries())) {
            result.append(createScalarSeriesComponent(*scalarSeries, plot));
        }
        else {
            qCDebug(LOG_GraphPlottablesFactory())
                << QObject::tr("Can't create graph plottables : unmanaged data series type");
        }
    }
    else {
        qCDebug(LOG_GraphPlottablesFactory())
            << QObject::tr("Can't create graph plottables : the variable is null");
    }

    return result;
}
