#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/qcustomplot.h"

#include <Common/ColorUtils.h>

#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphHelper, "VisualizationGraphHelper")

namespace {

class SqpDataContainer : public QCPGraphDataContainer {
public:
    void appendGraphData(const QCPGraphData &data) { mData.append(data); }
};


/// Format for datetimes on a axis
const auto DATETIME_TICKER_FORMAT = QStringLiteral("yyyy/MM/dd \nhh:mm:ss");

/// Generates the appropriate ticker for an axis, depending on whether the axis displays time or
/// non-time data
QSharedPointer<QCPAxisTicker> axisTicker(bool isTimeAxis)
{
    if (isTimeAxis) {
        auto dateTicker = QSharedPointer<QCPAxisTickerDateTime>::create();
        dateTicker->setDateTimeFormat(DATETIME_TICKER_FORMAT);
        dateTicker->setDateTimeSpec(Qt::UTC);

        return dateTicker;
    }
    else {
        // default ticker
        return QSharedPointer<QCPAxisTicker>::create();
    }
}

/// Sets axes properties according to the properties of a data series
template <int Dim>
void setAxesProperties(const DataSeries<Dim> &dataSeries, QCustomPlot &plot) noexcept
{
    /// @todo : for the moment, no control is performed on the axes: the units and the tickers
    /// are fixed for the default x-axis and y-axis of the plot, and according to the new graph
    auto setAxisProperties = [](auto axis, const auto &unit) {
        // label (unit name)
        axis->setLabel(unit.m_Name);

        // ticker (depending on the type of unit)
        axis->setTicker(axisTicker(unit.m_TimeUnit));
    };
    setAxisProperties(plot.xAxis, dataSeries.xAxisUnit());
    setAxisProperties(plot.yAxis, dataSeries.valuesUnit());
}

/**
 * Struct used to create plottables, depending on the type of the data series from which to create them
 * @tparam T the data series' type
 * @remarks Default implementation can't create plottables
 */
template <typename T, typename Enabled = void>
struct PlottablesCreator {
    static PlottablesMap createPlottables(T &, QCustomPlot &)
    {
        qCCritical(LOG_DataSeries())
            << QObject::tr("Can't create plottables: unmanaged data series type");
        return {};
    }
};

/**
 * Specialization of PlottablesCreator for scalars and vectors
 * @sa ScalarSeries
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesCreator<T,
                         typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value
                                                   or std::is_base_of<VectorSeries, T>::value> > {
    static PlottablesMap createPlottables(T &dataSeries, QCustomPlot &plot)
    {
        PlottablesMap result{};

        // Gets the number of components of the data series
        auto componentCount = dataSeries.valuesData()->componentCount();

        auto colors = ColorUtils::colors(Qt::blue, Qt::red, componentCount);

        // For each component of the data series, creates a QCPGraph to add to the plot
        for (auto i = 0; i < componentCount; ++i) {
            auto graph = plot.addGraph();
            graph->setPen(QPen{colors.at(i)});

            result.insert({i, graph});
        }

        // Axes properties
        setAxesProperties(dataSeries, plot);

        plot.replot();

        return result;
    }
};

/**
 * Struct used to update plottables, depending on the type of the data series from which to update them
 * @tparam T the data series' type
 * @remarks Default implementation can't update plottables
 */
template <typename T, typename Enabled = void>
struct PlottablesUpdater {
    static void updatePlottables(T &, PlottablesMap &, const SqpRange &, bool)
    {
        qCCritical(LOG_DataSeries())
            << QObject::tr("Can't update plottables: unmanaged data series type");
    }
};

/**
 * Specialization of PlottablesUpdater for scalars and vectors
 * @sa ScalarSeries
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesUpdater<T,
                         typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value
                                                   or std::is_base_of<VectorSeries, T>::value> > {
    static void updatePlottables(T &dataSeries, PlottablesMap &plottables, const SqpRange &range,
                                 bool rescaleAxes)
    {
        dataSeries.lockRead();

        // For each plottable to update, resets its data
        std::map<int, QSharedPointer<SqpDataContainer> > dataContainers{};
        for (const auto &plottable : plottables) {
            if (auto graph = dynamic_cast<QCPGraph *>(plottable.second)) {
                auto dataContainer = QSharedPointer<SqpDataContainer>::create();
                graph->setData(dataContainer);

                dataContainers.insert({plottable.first, dataContainer});
            }
        }

        // - Gets the data of the series included in the current range
        // - Updates each plottable by adding, for each data item, a point that takes x-axis data and value data. The correct value is retrieved according to the index of the component
        auto subDataIts = dataSeries.subData(range.m_TStart, range.m_TEnd);
        for (auto it = subDataIts.first; it != subDataIts.second; ++it) {
            for (const auto &dataContainer : dataContainers) {
                auto componentIndex = dataContainer.first;
                dataContainer.second->appendGraphData(
                    QCPGraphData(it->x(), it->value(componentIndex)));
            }
        }

        dataSeries.unlock();

        if (!plottables.empty()) {
            auto plot = plottables.begin()->second->parentPlot();

            if (rescaleAxes) {
                plot->rescaleAxes();
            }

            plot->replot();
        }
    }
};

/**
 * Helper used to create/update plottables
 */
struct IPlottablesHelper {
    virtual ~IPlottablesHelper() noexcept = default;
    virtual PlottablesMap create(QCustomPlot &plot) const = 0;
    virtual void update(PlottablesMap &plottables, const SqpRange &range,
                        bool rescaleAxes = false) const = 0;
};

/**
 * Default implementation of IPlottablesHelper, which takes data series to create/update plottables
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper {
    explicit PlottablesHelper(T &dataSeries) : m_DataSeries{dataSeries} {}

    PlottablesMap create(QCustomPlot &plot) const override
    {
        return PlottablesCreator<T>::createPlottables(m_DataSeries, plot);
    }

    void update(PlottablesMap &plottables, const SqpRange &range, bool rescaleAxes) const override
    {
        PlottablesUpdater<T>::updatePlottables(m_DataSeries, plottables, range, rescaleAxes);
    }

    T &m_DataSeries;
};

/// Creates IPlottablesHelper according to a data series
std::unique_ptr<IPlottablesHelper> createHelper(IDataSeries *dataSeries) noexcept
{
    if (auto scalarSeries = dynamic_cast<ScalarSeries *>(dataSeries)) {
        return std::make_unique<PlottablesHelper<ScalarSeries> >(*scalarSeries);
    }
    else if (auto vectorSeries = dynamic_cast<VectorSeries *>(dataSeries)) {
        return std::make_unique<PlottablesHelper<VectorSeries> >(*vectorSeries);
    }
    else {
        return std::make_unique<PlottablesHelper<IDataSeries> >(*dataSeries);
    }
}

} // namespace

PlottablesMap VisualizationGraphHelper::create(std::shared_ptr<Variable> variable,
                                               QCustomPlot &plot) noexcept
{
    if (variable) {
        auto helper = createHelper(variable->dataSeries().get());
        auto plottables = helper->create(plot);
        return plottables;
    }
    else {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't create graph plottables : the variable is null");
        return PlottablesMap{};
    }
}

void VisualizationGraphHelper::updateData(PlottablesMap &plottables, IDataSeries *dataSeries,
                                          const SqpRange &dateTime)
{
    auto helper = createHelper(dataSeries);
    helper->update(plottables, dateTime);
}
