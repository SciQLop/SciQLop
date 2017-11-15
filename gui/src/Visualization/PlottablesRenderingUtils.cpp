#include "Visualization/PlottablesRenderingUtils.h"

#include <Common/ColorUtils.h>

#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/VectorSeries.h>

#include <Visualization/qcustomplot.h>

Q_LOGGING_CATEGORY(LOG_PlottablesRenderingUtils, "PlottablesRenderingUtils")

namespace {

/// Default gradient used for colormap
const auto DEFAULT_COLORMAP_GRADIENT = QCPColorGradient::gpJet;

/**
 * Delegate used to set plottables properties
 */
template <typename T, typename Enabled = void>
struct PlottablesSetter {
    static void setProperties(T &, PlottablesMap &)
    {
        // Default implementation does nothing
        qCCritical(LOG_PlottablesRenderingUtils())
            << "Can't set plottables properties: unmanaged type of data";
    }
};

/**
 * Specialization of PlottablesSetter for scalars and vectors
 * @sa ScalarSeries
 * @sa VectorSeries
 */
template <typename T>
struct PlottablesSetter<T, typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value
                                                     or std::is_base_of<VectorSeries, T>::value> > {
    static void setProperties(T &dataSeries, PlottablesMap &plottables)
    {
        // Gets the number of components of the data series
        dataSeries.lockRead();
        auto componentCount = dataSeries.valuesData()->componentCount();
        dataSeries.unlock();

        // Generates colors for each component
        auto colors = ColorUtils::colors(Qt::blue, Qt::red, componentCount);

        // For each component of the data series, creates a QCPGraph to add to the plot
        for (auto i = 0; i < componentCount; ++i) {
            auto graph = plottables.at(i);
            graph->setPen(QPen{colors.at(i)});
        }
    }
};

/**
 * Specialization of PlottablesSetter for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesSetter<T,
                        typename std::enable_if_t<std::is_base_of<SpectrogramSeries, T>::value> > {
    static void setProperties(T &, PlottablesMap &plottables)
    {
        // Checks that for a spectrogram there is only one plottable, that is a colormap
        if (plottables.size() != 1) {
            return;
        }

        if (auto colormap = dynamic_cast<QCPColorMap *>(plottables.begin()->second)) {
            colormap->setInterpolate(false); // No value interpolation
            colormap->setTightBoundary(true);

            // Finds color scale in the colormap's plot to associate with it
            auto plot = colormap->parentPlot();
            auto plotElements = plot->plotLayout()->elements(false);
            for (auto plotElement : plotElements) {
                if (auto colorScale = dynamic_cast<QCPColorScale *>(plotElement)) {
                    colormap->setColorScale(colorScale);
                }
            }

            // Sets gradient used for color scale
            colormap->setGradient(DEFAULT_COLORMAP_GRADIENT);
            colormap->rescaleDataRange();
        }
        else {
            qCCritical(LOG_PlottablesRenderingUtils()) << "Can't get colormap of the spectrogram";
        }
    }
};

/**
 * Default implementation of IPlottablesHelper, which takes data series to set plottables properties
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper {
    explicit PlottablesHelper(T &dataSeries) : m_DataSeries{dataSeries} {}

    void setProperties(PlottablesMap &plottables) override
    {
        PlottablesSetter<T>::setProperties(m_DataSeries, plottables);
    }

    T &m_DataSeries;
};

} // namespace

std::unique_ptr<IPlottablesHelper>
IPlottablesHelperFactory::create(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    if (auto scalarSeries = std::dynamic_pointer_cast<ScalarSeries>(dataSeries)) {
        return std::make_unique<PlottablesHelper<ScalarSeries> >(*scalarSeries);
    }
    else if (auto spectrogramSeries = std::dynamic_pointer_cast<SpectrogramSeries>(dataSeries)) {
        return std::make_unique<PlottablesHelper<SpectrogramSeries> >(*spectrogramSeries);
    }
    else if (auto vectorSeries = std::dynamic_pointer_cast<VectorSeries>(dataSeries)) {
        return std::make_unique<PlottablesHelper<VectorSeries> >(*vectorSeries);
    }
    else {
        return std::make_unique<PlottablesHelper<IDataSeries> >(*dataSeries);
    }
}
