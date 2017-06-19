#include "Visualization/GraphPlottablesFactory.h"
#include "Visualization/qcustomplot.h"

#include <Data/ScalarSeries.h>

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_GraphPlottablesFactory, "GraphPlottablesFactory")

namespace {

/// Format for datetimes on a axis
const auto DATETIME_TICKER_FORMAT = QStringLiteral("yyyy/MM/dd \nhh:mm:ss");

/// Generates the appropriate ticker for an axis, depending on whether the axis displays time or
/// non-time data
QSharedPointer<QCPAxisTicker> axisTicker(bool isTimeAxis)
{
    if (isTimeAxis) {
        auto dateTicker = QSharedPointer<QCPAxisTickerDateTime>::create();
        dateTicker->setDateTimeFormat(DATETIME_TICKER_FORMAT);

        return dateTicker;
    }
    else {
        // default ticker
        return QSharedPointer<QCPAxisTicker>::create();
    }
}

QCPAbstractPlottable *createScalarSeriesComponent(ScalarSeries &scalarSeries, QCustomPlot &plot)
{
    auto component = plot.addGraph();

    if (component) {
        // Graph data
        component->setData(scalarSeries.xAxisData()->data(), scalarSeries.valuesData()->data(),
                           true);

        // Axes properties
        /// @todo : for the moment, no control is performed on the axes: the units and the tickers
        /// are fixed for the default x-axis and y-axis of the plot, and according to the new graph

        auto setAxisProperties = [](auto axis, const auto &unit) {
            // label (unit name)
            axis->setLabel(unit.m_Name);

            // ticker (depending on the type of unit)
            axis->setTicker(axisTicker(unit.m_TimeUnit));
        };
        setAxisProperties(plot.xAxis, scalarSeries.xAxisUnit());
        setAxisProperties(plot.yAxis, scalarSeries.valuesUnit());

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
