#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/qcustomplot.h"

#include <Data/ScalarTimeSerie.h>
#include <Data/SpectrogramTimeSerie.h>
#include <Data/TimeSeriesUtils.h>
#include <Data/VectorTimeSerie.h>

#include <Common/cpp_utils.h>
#include <Variable/Variable2.h>
#include <algorithm>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphHelper, "VisualizationGraphHelper")

namespace
{

class SqpDataContainer : public QCPGraphDataContainer
{
public:
    void appendGraphData(const QCPGraphData& data) { mData.append(data); }
};

/**
 * Struct used to create plottables, depending on the type of the data series from which to create
 * them
 * @tparam T the data series' type
 * @remarks Default implementation can't create plottables
 */
template <typename T, typename Enabled = void>
struct PlottablesCreator
{
    static PlottablesMap createPlottables(QCustomPlot&, const std::shared_ptr<T>& dataSeries)
    {
        return {};
    }
};

PlottablesMap createGraphs(QCustomPlot& plot, int nbGraphs)
{
    PlottablesMap result {};

    // Creates {nbGraphs} QCPGraph to add to the plot
    for (auto i = 0; i < nbGraphs; ++i)
    {
        auto graph = plot.addGraph();
        result.insert({ i, graph });
    }

    plot.replot();

    return result;
}

/**
 * Specialization of PlottablesCreator for scalars
 * @sa ScalarSeries
 */
template <typename T>
struct PlottablesCreator<T, typename std::enable_if_t<std::is_base_of<ScalarTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot, const std::shared_ptr<T>& dataSeries)
    {
        return createGraphs(plot, 1);
    }
};

/**
 * Specialization of PlottablesCreator for vectors
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesCreator<T, typename std::enable_if_t<std::is_base_of<VectorTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot, const std::shared_ptr<T>& dataSeries)
    {
        return createGraphs(plot, 3);
    }
};

/**
 * Specialization of PlottablesCreator for MultiComponentTimeSeries
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesCreator<T,
    typename std::enable_if_t<std::is_base_of<MultiComponentTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot, const std::shared_ptr<T>& dataSeries)
    {
        return createGraphs(plot, dataSeries->size(1));
    }
};

/**
 * Specialization of PlottablesCreator for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesCreator<T,
    typename std::enable_if_t<std::is_base_of<SpectrogramTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot, const std::shared_ptr<T>& dataSeries)
    {
        PlottablesMap result {};
        result.insert({ 0, new QCPColorMap { plot.xAxis, plot.yAxis } });

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
struct PlottablesUpdater
{
    static void setPlotYAxisRange(T&, const DateTimeRange&, QCustomPlot&)
    {
        qCCritical(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't set plot y-axis range: unmanaged data series type");
    }

    static void updatePlottables(T&, PlottablesMap&, const DateTimeRange&, bool)
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
struct PlottablesUpdater<T, typename std::enable_if_t<std::is_base_of<ScalarTimeSerie, T>::value>>
{
    static void setPlotYAxisRange(T& dataSeries, const DateTimeRange& xAxisRange, QCustomPlot& plot)
    {
        auto minValue = 0., maxValue = 0.;
        if (auto serie = dynamic_cast<ScalarTimeSerie*>(&dataSeries))
        {
            if (serie->size())
            {
                maxValue = (*std::max_element(std::begin(*serie), std::end(*serie))).v();
                minValue = (*std::min_element(std::begin(*serie), std::end(*serie))).v();
            }
        }
        plot.yAxis->setRange(QCPRange { minValue, maxValue });
    }

    static void updatePlottables(
        T& dataSeries, PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes)
    {

        // For each plottable to update, resets its data
        for (const auto& plottable : plottables)
        {
            if (auto graph = dynamic_cast<QCPGraph*>(plottable.second))
            {
                auto dataContainer = QSharedPointer<SqpDataContainer>::create();
                if (auto serie = dynamic_cast<ScalarTimeSerie*>(&dataSeries))
                {
                    std::for_each(
                        std::begin(*serie), std::end(*serie), [&dataContainer](const auto& value) {
                            dataContainer->appendGraphData(QCPGraphData(value.t(), value.v()));
                        });
                }
                graph->setData(dataContainer);
            }
        }

        if (!plottables.empty())
        {
            auto plot = plottables.begin()->second->parentPlot();

            if (rescaleAxes)
            {
                plot->rescaleAxes();
            }
        }
    }
};


template <typename T>
struct PlottablesUpdater<T, typename std::enable_if_t<std::is_base_of<VectorTimeSerie, T>::value>>
{
    static void setPlotYAxisRange(T& dataSeries, const DateTimeRange& xAxisRange, QCustomPlot& plot)
    {
        double minValue = 0., maxValue = 0.;
        if (auto serie = dynamic_cast<VectorTimeSerie*>(&dataSeries))
        {
            std::for_each(
                std::begin(*serie), std::end(*serie), [&minValue, &maxValue](const auto& v) {
                    minValue = std::min({ minValue, v.v().x, v.v().y, v.v().z });
                    maxValue = std::max({ maxValue, v.v().x, v.v().y, v.v().z });
                });
        }

        plot.yAxis->setRange(QCPRange { minValue, maxValue });
    }

    static void updatePlottables(
        T& dataSeries, PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes)
    {

        // For each plottable to update, resets its data
        for (const auto& plottable : plottables)
        {
            if (auto graph = dynamic_cast<QCPGraph*>(plottable.second))
            {
                auto dataContainer = QSharedPointer<SqpDataContainer>::create();
                if (auto serie = dynamic_cast<VectorTimeSerie*>(&dataSeries))
                {
                    switch (plottable.first)
                    {
                        case 0:
                            std::for_each(std::begin(*serie), std::end(*serie),
                                [&dataContainer](const auto& value) {
                                    dataContainer->appendGraphData(
                                        QCPGraphData(value.t(), value.v().x));
                                });
                            break;
                        case 1:
                            std::for_each(std::begin(*serie), std::end(*serie),
                                [&dataContainer](const auto& value) {
                                    dataContainer->appendGraphData(
                                        QCPGraphData(value.t(), value.v().y));
                                });
                            break;
                        case 2:
                            std::for_each(std::begin(*serie), std::end(*serie),
                                [&dataContainer](const auto& value) {
                                    dataContainer->appendGraphData(
                                        QCPGraphData(value.t(), value.v().z));
                                });
                            break;
                        default:
                            break;
                    }
                }
                graph->setData(dataContainer);
            }
        }

        if (!plottables.empty())
        {
            auto plot = plottables.begin()->second->parentPlot();

            if (rescaleAxes)
            {
                plot->rescaleAxes();
            }
        }
    }
};


template <typename T>
struct PlottablesUpdater<T,
    typename std::enable_if_t<std::is_base_of<MultiComponentTimeSerie, T>::value>>
{
    static void setPlotYAxisRange(T& dataSeries, const DateTimeRange& xAxisRange, QCustomPlot& plot)
    {
        double minValue = 0., maxValue = 0.;
        if (auto serie = dynamic_cast<MultiComponentTimeSerie*>(&dataSeries))
        {
            std::for_each(
                std::begin(*serie), std::end(*serie), [&minValue, &maxValue](const auto& v) {
                    minValue = std::min(minValue, std::min_element(v.begin(), v.end())->v());
                    maxValue = std::max(maxValue, std::max_element(v.begin(), v.end())->v());
                });
        }
        plot.yAxis->setRange(QCPRange { minValue, maxValue });
    }

    static void updatePlottables(
        T& dataSeries, PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes)
    {
        for (const auto& plottable : plottables)
        {
            if (auto graph = dynamic_cast<QCPGraph*>(plottable.second))
            {
                auto dataContainer = QSharedPointer<SqpDataContainer>::create();
                if (auto serie = dynamic_cast<MultiComponentTimeSerie*>(&dataSeries))
                {
                    // TODO
                    std::for_each(std::begin(*serie), std::end(*serie),
                        [&dataContainer, component = plottable.first](const auto& value) {
                            dataContainer->appendGraphData(
                                QCPGraphData(value.t(), value[component]));
                        });
                }
                graph->setData(dataContainer);
            }
        }

        if (!plottables.empty())
        {
            auto plot = plottables.begin()->second->parentPlot();

            if (rescaleAxes)
            {
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
    typename std::enable_if_t<std::is_base_of<SpectrogramTimeSerie, T>::value>>
{
    static void setPlotYAxisRange(T& dataSeries, const DateTimeRange& xAxisRange, QCustomPlot& plot)
    {
        auto [minValue, maxValue] = dataSeries.axis_range(1);
        std::cout << "min=" << minValue << "   max=" << maxValue << std::endl;
        plot.yAxis->setRange(QCPRange { minValue, maxValue });
    }

    static void updatePlottables(
        T& dataSeries, PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes)
    {
        if (plottables.empty())
        {
            qCDebug(LOG_VisualizationGraphHelper())
                << QObject::tr("Can't update spectrogram: no colormap has been associated");
            return;
        }

        // Gets the colormap to update (normally there is only one colormap)
        Q_ASSERT(plottables.size() == 1);
        auto colormap = dynamic_cast<QCPColorMap*>(plottables.at(0));
        Q_ASSERT(colormap != nullptr);
        auto plot = colormap->parentPlot();
        auto [minValue, maxValue] = dataSeries.axis_range(1);
        plot->yAxis->setRange(QCPRange { minValue, maxValue });
        if (auto serie = dynamic_cast<SpectrogramTimeSerie*>(&dataSeries))
        {
            if (serie->size(0) > 2)
            {
                const auto& xAxis = serie->axis(0);
                auto yAxis = serie->axis(1); // copy for in place reverse order
                std::reverse(std::begin(yAxis), std::end(yAxis));
                auto xAxisProperties = TimeSeriesUtils::axis_analysis<TimeSeriesUtils::IsLinear,
                    TimeSeriesUtils::CheckMedian>(xAxis);
                auto yAxisProperties = TimeSeriesUtils::axis_analysis<TimeSeriesUtils::IsLog,
                    TimeSeriesUtils::DontCheckMedian>(yAxis);

                int colormap_h_size = std::min(32000,
                    static_cast<int>(xAxisProperties.range / xAxisProperties.max_resolution));
                auto colormap_v_size
                    = static_cast<int>(yAxisProperties.range / yAxisProperties.max_resolution);

                colormap->data()->setSize(colormap_h_size, colormap_v_size);
                colormap->data()->setRange(
                    QCPRange { serie->begin()->t(), (serie->end() - 1)->t() },
                    { minValue, maxValue });

                std::vector<std::pair<int, int>> y_access_pattern;
                for (int y_index = 0, cel_index = 0; y_index < colormap_v_size; y_index++)
                {
                    double current_y = pow(
                        10., (yAxisProperties.max_resolution * y_index) + std::log10(minValue));
                    if (current_y > yAxis[cel_index])
                        cel_index++;
                    y_access_pattern.push_back({ y_index, yAxis.size() - 1 - cel_index });
                }

                auto line = serie->begin();
                double current_time = xAxis[0];
                int x_index = 0;

                while (x_index < colormap_h_size)
                {
                    if (current_time > (line + 1)->t())
                    {
                        line++;
                    }
                    if ((current_time - xAxis[0])
                        > (x_index * xAxisProperties.range / colormap_h_size))
                    {
                        x_index++;
                    }
                    if (line->t() <= (current_time + xAxisProperties.max_resolution))
                    {
                        std::for_each(std::cbegin(y_access_pattern), std::cend(y_access_pattern),
                            [&colormap, &line, x_index](const auto& acc) {
                                colormap->data()->setCell(x_index, acc.first, (*line)[acc.second]);
                            });
                    }
                    else
                    {
                        for (int y_index = 0; y_index < colormap_v_size; y_index++)
                        {
                            colormap->data()->setCell(x_index, y_index, std::nan(""));
                        }
                    }
                    current_time += xAxisProperties.max_resolution;
                }
            }

            if (rescaleAxes)
            {
                plot->rescaleAxes();
            }
        }
    }
};

/**
 * Helper used to create/update plottables
 */
struct IPlottablesHelper
{
    virtual ~IPlottablesHelper() noexcept = default;
    virtual PlottablesMap create(QCustomPlot& plot) const = 0;
    virtual void setYAxisRange(const DateTimeRange& xAxisRange, QCustomPlot& plot) const = 0;
    virtual void update(
        PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes = false) const = 0;
};

/**
 * Default implementation of IPlottablesHelper, which takes data series to create/update
 * plottables
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper
{
    explicit PlottablesHelper(std::shared_ptr<T> dataSeries) : m_DataSeries { dataSeries } {}

    PlottablesMap create(QCustomPlot& plot) const override
    {
        return PlottablesCreator<T>::createPlottables(plot, m_DataSeries);
    }

    void update(
        PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes) const override
    {
        if (m_DataSeries)
        {
            PlottablesUpdater<T>::updatePlottables(*m_DataSeries, plottables, range, rescaleAxes);
        }
        else
        {
            qCCritical(LOG_VisualizationGraphHelper()) << "Can't update plottables: inconsistency "
                                                          "between the type of data series and the "
                                                          "type supposed";
        }
    }

    void setYAxisRange(const DateTimeRange& xAxisRange, QCustomPlot& plot) const override
    {
        if (m_DataSeries)
        {
            PlottablesUpdater<T>::setPlotYAxisRange(*m_DataSeries, xAxisRange, plot);
        }
        else
        {
            qCCritical(LOG_VisualizationGraphHelper()) << "Can't update plottables: inconsistency "
                                                          "between the type of data series and the "
                                                          "type supposed";
        }
    }

    std::shared_ptr<T> m_DataSeries;
};

/// Creates IPlottablesHelper according to the type of data series a variable holds
std::unique_ptr<IPlottablesHelper> createHelper(std::shared_ptr<Variable2> variable) noexcept
{
    switch (variable->type())
    {
        case DataSeriesType::SCALAR:
            return std::make_unique<PlottablesHelper<ScalarTimeSerie>>(
                std::dynamic_pointer_cast<ScalarTimeSerie>(variable->data()));
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<PlottablesHelper<SpectrogramTimeSerie>>(
                std::dynamic_pointer_cast<SpectrogramTimeSerie>(variable->data()));
        case DataSeriesType::VECTOR:
            return std::make_unique<PlottablesHelper<VectorTimeSerie>>(
                std::dynamic_pointer_cast<VectorTimeSerie>(variable->data()));
        case DataSeriesType::MULTICOMPONENT:
            return std::make_unique<PlottablesHelper<MultiComponentTimeSerie>>(
                std::dynamic_pointer_cast<MultiComponentTimeSerie>(variable->data()));
        default:
            // Creates default helper
            break;
    }

    return std::make_unique<PlottablesHelper<TimeSeries::ITimeSerie>>(nullptr);
}

} // namespace

PlottablesMap VisualizationGraphHelper::create(
    std::shared_ptr<Variable2> variable, QCustomPlot& plot) noexcept
{
    if (variable)
    {
        auto helper = createHelper(variable);
        auto plottables = helper->create(plot);
        return plottables;
    }
    else
    {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't create graph plottables : the variable is null");
        return PlottablesMap {};
    }
}

void VisualizationGraphHelper::setYAxisRange(
    std::shared_ptr<Variable2> variable, QCustomPlot& plot) noexcept
{
    if (variable)
    {
        auto helper = createHelper(variable);
        helper->setYAxisRange(variable->range(), plot);
    }
    else
    {
        qCDebug(LOG_VisualizationGraphHelper())
            << QObject::tr("Can't set y-axis range of plot: the variable is null");
    }
}

void VisualizationGraphHelper::updateData(
    PlottablesMap& plottables, std::shared_ptr<Variable2> variable, const DateTimeRange& dateTime)
{
    auto helper = createHelper(variable);
    helper->update(plottables, dateTime);
}
