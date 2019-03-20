#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/qcustomplot.h"

#include <Data/DataSeriesUtils.h>
#include <Data/ScalarTimeSerie.h>
#include <Data/SpectrogramTimeSerie.h>
#include <Data/VectorTimeSerie.h>

#include <Variable/Variable2.h>

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
    static PlottablesMap createPlottables(QCustomPlot&) { return {}; }
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
    static PlottablesMap createPlottables(QCustomPlot& plot) { return createGraphs(plot, 1); }
};

/**
 * Specialization of PlottablesCreator for vectors
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesCreator<T, typename std::enable_if_t<std::is_base_of<VectorTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot) { return createGraphs(plot, 3); }
};

/**
 * Specialization of PlottablesCreator for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesCreator<T,
    typename std::enable_if_t<std::is_base_of<SpectrogramTimeSerie, T>::value>>
{
    static PlottablesMap createPlottables(QCustomPlot& plot)
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
            maxValue = (*std::max_element(std::begin(*serie), std::end(*serie))).v();
            minValue = (*std::min_element(std::begin(*serie), std::end(*serie))).v();
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
        // TODO
        //        double min, max;
        //        std::tie(min, max) = dataSeries.yBounds();

        //        if (!std::isnan(min) && !std::isnan(max))
        //        {
        //            plot.yAxis->setRange(QCPRange { min, max });
        //        }
    }

    static void updatePlottables(
        T& dataSeries, PlottablesMap& plottables, const DateTimeRange& range, bool rescaleAxes)
    {
        // TODO
        //        if (plottables.empty())
        //        {
        //            qCDebug(LOG_VisualizationGraphHelper())
        //                << QObject::tr("Can't update spectrogram: no colormap has been
        //                associated");
        //            return;
        //        }

        //        // Gets the colormap to update (normally there is only one colormap)
        //        Q_ASSERT(plottables.size() == 1);
        //        auto colormap = dynamic_cast<QCPColorMap*>(plottables.at(0));
        //        Q_ASSERT(colormap != nullptr);

        //        dataSeries.lockRead();

        //        // Processing spectrogram data for display in QCustomPlot
        //        auto its = dataSeries.xAxisRange(range.m_TStart, range.m_TEnd);

        //        // Computes logarithmic y-axis resolution for the spectrogram
        //        auto yData = its.first->y();
        //        auto yResolution = DataSeriesUtils::resolution(yData.begin(), yData.end(), true);

        //        // Generates mesh for colormap
        //        auto mesh = DataSeriesUtils::regularMesh(its.first, its.second,
        //            DataSeriesUtils::Resolution { dataSeries.xResolution() }, yResolution);

        //        dataSeries.unlock();

        //        colormap->data()->setSize(mesh.m_NbX, mesh.m_NbY);
        //        if (!mesh.isEmpty())
        //        {
        //            colormap->data()->setRange(QCPRange { mesh.m_XMin, mesh.xMax() },
        //                // y-axis range is converted to linear values
        //                QCPRange { std::pow(10, mesh.m_YMin), std::pow(10, mesh.yMax()) });

        //            // Sets values
        //            auto index = 0;
        //            for (auto it = mesh.m_Data.begin(), end = mesh.m_Data.end(); it != end; ++it,
        //            ++index)
        //            {
        //                auto xIndex = index % mesh.m_NbX;
        //                auto yIndex = index / mesh.m_NbX;

        //                colormap->data()->setCell(xIndex, yIndex, *it);

        //                // Makes the NaN values to be transparent in the colormap
        //                if (std::isnan(*it))
        //                {
        //                    colormap->data()->setAlpha(xIndex, yIndex, 0);
        //                }
        //            }
        //        }

        //        // Rescales axes
        //        auto plot = colormap->parentPlot();

        //        if (rescaleAxes)
        //        {
        //            plot->rescaleAxes();
        //        }
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
 * Default implementation of IPlottablesHelper, which takes data series to create/update plottables
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper
{
    explicit PlottablesHelper(T* dataSeries) : m_DataSeries { dataSeries } {}

    PlottablesMap create(QCustomPlot& plot) const override
    {
        return PlottablesCreator<T>::createPlottables(plot);
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

    T* m_DataSeries;
};

/// Creates IPlottablesHelper according to the type of data series a variable holds
std::unique_ptr<IPlottablesHelper> createHelper(std::shared_ptr<Variable2> variable) noexcept
{
    switch (variable->type())
    {
        case DataSeriesType::SCALAR:
            return std::make_unique<PlottablesHelper<ScalarTimeSerie>>(
                dynamic_cast<ScalarTimeSerie*>(variable->data()->base()));
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<PlottablesHelper<SpectrogramTimeSerie>>(
                dynamic_cast<SpectrogramTimeSerie*>(variable->data()->base()));
        case DataSeriesType::VECTOR:
            return std::make_unique<PlottablesHelper<VectorTimeSerie>>(
                dynamic_cast<VectorTimeSerie*>(variable->data()->base()));
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
