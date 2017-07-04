#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/qcustomplot.h"

#include <Data/ScalarSeries.h>

#include <Variable/Variable.h>

#include <QElapsedTimer>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphHelper, "VisualizationGraphHelper")

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

void updateScalarData(QCPAbstractPlottable *component, ScalarSeries &scalarSeries,
                      const SqpDateTime &dateTime)
{
    if (auto qcpGraph = dynamic_cast<QCPGraph *>(component)) {
        // Clean the graph
        // NAIVE approch
        const auto xData = scalarSeries.xAxisData()->data();
        const auto valuesData = scalarSeries.valuesData()->data();
        const auto count = xData.count();
        qCInfo(LOG_VisualizationGraphHelper()) << "TORM: Current points in cache" << xData.count();
        auto xValue = QVector<double>(count);
        auto vValue = QVector<double>(count);

        int n = 0;
        for (auto i = 0; i < count; ++i) {
            const auto x = xData[i];
            if (x >= dateTime.m_TStart && x <= dateTime.m_TEnd) {
                xValue[n] = x;
                vValue[n] = valuesData[i];
                ++n;
            }
        }

        xValue.resize(n);
        vValue.resize(n);

        qCInfo(LOG_VisualizationGraphHelper()) << "TORM: Current points displayed"
                                               << xValue.count();

        qcpGraph->setData(xValue, vValue);

        // Display all data
        component->rescaleAxes();
        component->parentPlot()->replot();
    }
    else {
        /// @todo DEBUG
    }
}

QCPAbstractPlottable *createScalarSeriesComponent(ScalarSeries &scalarSeries, QCustomPlot &plot,
                                                  const SqpDateTime &dateTime)
{
    auto component = plot.addGraph();

    if (component) {
        //        // Graph data
        component->setData(scalarSeries.xAxisData()->data(), scalarSeries.valuesData()->data(),
                           true);

        updateScalarData(component, scalarSeries, dateTime);

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
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't create graph for the scalar series");
    }

    return component;
}

} // namespace

QVector<QCPAbstractPlottable *> VisualizationGraphHelper::create(std::shared_ptr<Variable> variable,
                                                                 QCustomPlot &plot) noexcept
{
    auto result = QVector<QCPAbstractPlottable *>{};

    if (variable) {
        // Gets the data series of the variable to call the creation of the right components
        // according to its type
        if (auto scalarSeries = dynamic_cast<ScalarSeries *>(variable->dataSeries())) {
            result.append(createScalarSeriesComponent(*scalarSeries, plot, variable->dateTime()));
        }
        else {
            qCDebug(LOG_VisualizationGraphHelper())
                << QObject::tr("Can't create graph plottables : unmanaged data series type");
        }
    }
    else {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't create graph plottables : the variable is null");
    }

    return result;
}

void VisualizationGraphHelper::updateData(QVector<QCPAbstractPlottable *> plotableVect,
                                          IDataSeries *dataSeries, const SqpDateTime &dateTime)
{
    if (auto scalarSeries = dynamic_cast<ScalarSeries *>(dataSeries)) {
        if (plotableVect.size() == 1) {
            updateScalarData(plotableVect.at(0), *scalarSeries, dateTime);
        }
        else {
            qCCritical(LOG_VisualizationGraphHelper()) << QObject::tr(
                "Can't update Data of a scalarSeries because there is not only one component "
                "associated");
        }
    }
    else {
        /// @todo DEBUG
    }
}
