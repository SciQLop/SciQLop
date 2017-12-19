#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/qcustomplot.h"

#include <Data/DataSeriesUtils.h>
#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/VectorSeries.h>

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphHelper, "VisualizationGraphHelper")

namespace {

class SqpDataContainer : public QCPGraphDataContainer {
public:
    void appendGraphData(const QCPGraphData &data) { mData.append(data); }
};

/**
 * Struct used to create plottables, depending on the type of the data series from which to create
 * them
 * @tparam T the data series' type
 * @remarks Default implementation can't create plottables
 */
template <typename T, typename Enabled = void>
struct PlottablesCreator {
    static PlottablesMap createPlottables(QCustomPlot &)
    {
        qCCritical(LOG_DataSeries())
            << QObject::tr("Can't create plottables: unmanaged data series type");
        return {};
    }
};

PlottablesMap createGraphs(QCustomPlot &plot, int nbGraphs)
{
    PlottablesMap result{};

    // Creates {nbGraphs} QCPGraph to add to the plot
    for (auto i = 0; i < nbGraphs; ++i) {
        auto graph = plot.addGraph();
        result.insert({i, graph});
    }

    plot.replot();

    return result;
}

/**
 * Specialization of PlottablesCreator for scalars
 * @sa ScalarSeries
 */
template <typename T>
struct PlottablesCreator<T, typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value> > {
    static PlottablesMap createPlottables(QCustomPlot &plot) { return createGraphs(plot, 1); }
};

/**
 * Specialization of PlottablesCreator for vectors
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesCreator<T, typename std::enable_if_t<std::is_base_of<VectorSeries, T>::value> > {
    static PlottablesMap createPlottables(QCustomPlot &plot) { return createGraphs(plot, 3); }
};

/**
 * Specialization of PlottablesCreator for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesCreator<T,
                         typename std::enable_if_t<std::is_base_of<SpectrogramSeries, T>::value> > {
    static PlottablesMap createPlottables(QCustomPlot &plot)
    {
        PlottablesMap result{};
        result.insert({0, new QCPColorMap{plot.xAxis, plot.yAxis}});

        plot.replot();

        return result;
    }
};

/**
 * Struct used to update plottables, depending on the type of the data series from which to update
 * them
 * @tparam T the data series' type
 * @remarks Default implementation can't update plottables
 */
template <typename T, typename Enabled = void>
struct PlottablesUpdater {
    static void setPlotYAxisRange(T &, const SqpRange &, QCustomPlot &)
    {
        qCCritical(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't set plot y-axis range: unmanaged data series type");
    }

    static void updatePlottables(T &, PlottablesMap &, const SqpRange &, bool)
    {
        qCCritical(LOG_VisualizationGraphHelper())
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
    static void setPlotYAxisRange(T &dataSeries, const SqpRange &xAxisRange, QCustomPlot &plot)
    {
        auto minValue = 0., maxValue = 0.;

        dataSeries.lockRead();
        auto valuesBounds = dataSeries.valuesBounds(xAxisRange.m_TStart, xAxisRange.m_TEnd);
        auto end = dataSeries.cend();
        if (valuesBounds.first != end && valuesBounds.second != end) {
            auto rangeValue = [](const auto &value) { return std::isnan(value) ? 0. : value; };

            minValue = rangeValue(valuesBounds.first->minValue());
            maxValue = rangeValue(valuesBounds.second->maxValue());
        }
        dataSeries.unlock();

        plot.yAxis->setRange(QCPRange{minValue, maxValue});
    }

    static void updatePlottables(T &dataSeries, PlottablesMap &plottables, const SqpRange &range,
                                 bool rescaleAxes)
    {

        // For each plottable to update, resets its data
        std::map<int, QSharedPointer<SqpDataContainer> > dataContainers{};
        for (const auto &plottable : plottables) {
            if (auto graph = dynamic_cast<QCPGraph *>(plottable.second)) {
                auto dataContainer = QSharedPointer<SqpDataContainer>::create();
                graph->setData(dataContainer);

                dataContainers.insert({plottable.first, dataContainer});
            }
        }
        dataSeries.lockRead();

        // - Gets the data of the series included in the current range
        // - Updates each plottable by adding, for each data item, a point that takes x-axis data
        // and value data. The correct value is retrieved according to the index of the component
        auto subDataIts = dataSeries.xAxisRange(range.m_TStart, range.m_TEnd);
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
        }
    }
};

/**
 * Specialization of PlottablesUpdater for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesUpdater<T,
                         typename std::enable_if_t<std::is_base_of<SpectrogramSeries, T>::value> > {
    static void setPlotYAxisRange(T &dataSeries, const SqpRange &xAxisRange, QCustomPlot &plot)
    {
        double min, max;
        std::tie(min, max) = dataSeries.yBounds();

        if (!std::isnan(min) && !std::isnan(max)) {
            plot.yAxis->setRange(QCPRange{min, max});
        }
    }

    static void updatePlottables(T &dataSeries, PlottablesMap &plottables, const SqpRange &range,
                                 bool rescaleAxes)
    {
        if (plottables.empty()) {
            qCDebug(LOG_VisualizationGraphHelper())
                << QObject::tr("Can't update spectrogram: no colormap has been associated");
            return;
        }

        // Gets the colormap to update (normally there is only one colormap)
        Q_ASSERT(plottables.size() == 1);
        auto colormap = dynamic_cast<QCPColorMap *>(plottables.at(0));
        Q_ASSERT(colormap != nullptr);

        dataSeries.lockRead();

        // Processing spectrogram data for display in QCustomPlot
        auto its = dataSeries.xAxisRange(range.m_TStart, range.m_TEnd);

        // Computes logarithmic y-axis resolution for the spectrogram
        auto yData = its.first->y();
        auto yResolution = DataSeriesUtils::resolution(yData.begin(), yData.end(), true);

        // Generates mesh for colormap
        auto mesh = DataSeriesUtils::regularMesh(
            its.first, its.second, DataSeriesUtils::Resolution{dataSeries.xResolution()},
            yResolution);

        dataSeries.unlock();

        colormap->data()->setSize(mesh.m_NbX, mesh.m_NbY);
        if (!mesh.isEmpty()) {
            colormap->data()->setRange(
                QCPRange{mesh.m_XMin, mesh.xMax()},
                // y-axis range is converted to linear values
                QCPRange{std::pow(10, mesh.m_YMin), std::pow(10, mesh.yMax())});

            // Sets values
            auto index = 0;
            for (auto it = mesh.m_Data.begin(), end = mesh.m_Data.end(); it != end; ++it, ++index) {
                auto xIndex = index % mesh.m_NbX;
                auto yIndex = index / mesh.m_NbX;

                colormap->data()->setCell(xIndex, yIndex, *it);

                // Makes the NaN values to be transparent in the colormap
                if (std::isnan(*it)) {
                    colormap->data()->setAlpha(xIndex, yIndex, 0);
                }
            }
        }

        // Rescales axes
        auto plot = colormap->parentPlot();

        if (rescaleAxes) {
            plot->rescaleAxes();
        }
    }
};

/**
 * Helper used to create/update plottables
 */
struct IPlottablesHelper {
    virtual ~IPlottablesHelper() noexcept = default;
    virtual PlottablesMap create(QCustomPlot &plot) const = 0;
    virtual void setYAxisRange(const SqpRange &xAxisRange, QCustomPlot &plot) const = 0;
    virtual void update(PlottablesMap &plottables, const SqpRange &range,
                        bool rescaleAxes = false) const = 0;
};

/**
 * Default implementation of IPlottablesHelper, which takes data series to create/update plottables
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper {
    explicit PlottablesHelper(std::shared_ptr<T> dataSeries) : m_DataSeries{dataSeries} {}

    PlottablesMap create(QCustomPlot &plot) const override
    {
        return PlottablesCreator<T>::createPlottables(plot);
    }

    void update(PlottablesMap &plottables, const SqpRange &range, bool rescaleAxes) const override
    {
        if (m_DataSeries) {
            PlottablesUpdater<T>::updatePlottables(*m_DataSeries, plottables, range, rescaleAxes);
        }
        else {
            qCCritical(LOG_VisualizationGraphHelper()) << "Can't update plottables: inconsistency "
                                                          "between the type of data series and the "
                                                          "type supposed";
        }
    }

    void setYAxisRange(const SqpRange &xAxisRange, QCustomPlot &plot) const override
    {
        if (m_DataSeries) {
            PlottablesUpdater<T>::setPlotYAxisRange(*m_DataSeries, xAxisRange, plot);
        }
        else {
            qCCritical(LOG_VisualizationGraphHelper()) << "Can't update plottables: inconsistency "
                                                          "between the type of data series and the "
                                                          "type supposed";
        }
    }

    std::shared_ptr<T> m_DataSeries;
};

/// Creates IPlottablesHelper according to the type of data series a variable holds
std::unique_ptr<IPlottablesHelper> createHelper(std::shared_ptr<Variable> variable) noexcept
{
    switch (variable->type()) {
        case DataSeriesType::SCALAR:
            return std::make_unique<PlottablesHelper<ScalarSeries> >(
                std::dynamic_pointer_cast<ScalarSeries>(variable->dataSeries()));
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<PlottablesHelper<SpectrogramSeries> >(
                std::dynamic_pointer_cast<SpectrogramSeries>(variable->dataSeries()));
        case DataSeriesType::VECTOR:
            return std::make_unique<PlottablesHelper<VectorSeries> >(
                std::dynamic_pointer_cast<VectorSeries>(variable->dataSeries()));
        default:
            // Creates default helper
            break;
    }

    return std::make_unique<PlottablesHelper<IDataSeries> >(nullptr);
}

} // namespace

PlottablesMap VisualizationGraphHelper::create(std::shared_ptr<Variable> variable,
                                               QCustomPlot &plot) noexcept
{
    if (variable) {
        auto helper = createHelper(variable);
        auto plottables = helper->create(plot);
        return plottables;
    }
    else {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't create graph plottables : the variable is null");
        return PlottablesMap{};
    }
}

void VisualizationGraphHelper::setYAxisRange(std::shared_ptr<Variable> variable,
                                             QCustomPlot &plot) noexcept
{
    if (variable) {
        auto helper = createHelper(variable);
        helper->setYAxisRange(variable->range(), plot);
    }
    else {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't set y-axis range of plot: the variable is null");
    }
}

void VisualizationGraphHelper::updateData(PlottablesMap &plottables,
                                          std::shared_ptr<Variable> variable,
                                          const SqpRange &dateTime)
{
    auto helper = createHelper(variable);
    helper->update(plottables, dateTime);
}
