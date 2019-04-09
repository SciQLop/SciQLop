#include "Visualization/PlottablesRenderingUtils.h"

#include <Common/ColorUtils.h>

#include <Variable/Variable2.h>

#include <Visualization/qcustomplot.h>

Q_LOGGING_CATEGORY(LOG_PlottablesRenderingUtils, "PlottablesRenderingUtils")

namespace
{

/**
 * Delegate used to set plottables properties
 */
template <typename T, typename Enabled = void>
struct PlottablesSetter
{
    static void setProperties(PlottablesMap&)
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
struct PlottablesSetter<T,
    typename std::enable_if_t<std::is_base_of<ScalarTimeSerie, T>::value
        or std::is_base_of<VectorTimeSerie, T>::value
        or std::is_base_of<MultiComponentTimeSerie, T>::value>>
{
    static void setProperties(PlottablesMap& plottables)
    {
        // Finds the plottable with the highest index to determine the number of colors to generate
        auto end = plottables.cend();
        auto maxPlottableIndexIt = std::max_element(plottables.cbegin(), end,
            [](const auto& it1, const auto& it2) { return it1.first < it2.first; });
        auto componentCount = maxPlottableIndexIt != end ? maxPlottableIndexIt->first + 1 : 0;

        // Generates colors for each component
        auto colors = ColorUtils::colors(Qt::blue, Qt::red, componentCount);

        // For each component of the data series, creates a QCPGraph to add to the plot
        for (auto i = 0; i < componentCount; ++i)
        {
            auto graphIt = plottables.find(i);
            if (graphIt != end)
            {
                graphIt->second->setPen(QPen { colors.at(i) });
            }
        }
    }
};

/**
 * Specialization of PlottablesSetter for spectrograms
 * @sa SpectrogramSeries
 */
template <typename T>
struct PlottablesSetter<T,
    typename std::enable_if_t<std::is_base_of<SpectrogramTimeSerie, T>::value>>
{
    static void setProperties(PlottablesMap& plottables)
    {
        // Checks that for a spectrogram there is only one plottable, that is a colormap
        if (plottables.size() != 1)
        {
            return;
        }

        if (auto colormap = dynamic_cast<QCPColorMap*>(plottables.begin()->second))
        {
            colormap->setInterpolate(false); // No value interpolation
            colormap->setTightBoundary(true);

            // Finds color scale in the colormap's plot to associate with it
            auto plot = colormap->parentPlot();
            auto plotElements = plot->plotLayout()->elements(false);
            for (auto plotElement : plotElements)
            {
                if (auto colorScale = dynamic_cast<QCPColorScale*>(plotElement))
                {
                    colormap->setColorScale(colorScale);
                }
            }

            colormap->rescaleDataRange();
        }
        else
        {
            qCCritical(LOG_PlottablesRenderingUtils()) << "Can't get colormap of the spectrogram";
        }
    }
};

/**
 * Default implementation of IPlottablesHelper, which takes data series to set plottables properties
 * @tparam T the data series' type
 */
template <typename T>
struct PlottablesHelper : public IPlottablesHelper
{
    void setProperties(PlottablesMap& plottables) override
    {
        PlottablesSetter<T>::setProperties(plottables);
    }
};

} // namespace

std::unique_ptr<IPlottablesHelper> IPlottablesHelperFactory::create(Variable2& variable) noexcept
{
    switch (variable.type())
    {
        case DataSeriesType::SCALAR:
            return std::make_unique<PlottablesHelper<ScalarTimeSerie>>();
        case DataSeriesType::SPECTROGRAM:
            return std::make_unique<PlottablesHelper<SpectrogramTimeSerie>>();
        case DataSeriesType::VECTOR:
            return std::make_unique<PlottablesHelper<VectorTimeSerie>>();
        case DataSeriesType::MULTICOMPONENT:
            return std::make_unique<PlottablesHelper<MultiComponentTimeSerie>>();
        default:
            // Returns default helper
            break;
    }

    return std::make_unique<PlottablesHelper<TimeSeries::ITimeSerie>>();
}
