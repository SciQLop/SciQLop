#include "Visualization/AxisRenderingUtils.h"

#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>

#include <Visualization/qcustomplot.h>

namespace {

/**
 * Delegate used to set axes properties
 */
template <typename T, typename Enabled = void>
struct AxisSetter {
    static void setProperties(T &, QCustomPlot &, QCPColorScale &)
    {
        // Default implementation does nothing
    }
};

/**
 * Specialization of AxisSetter for scalars and vectors
 * @sa ScalarSeries
 * @sa VectorSeries
 */
template <typename T>
struct AxisSetter<T, typename std::enable_if_t<std::is_base_of<ScalarSeries, T>::value
                                               or std::is_base_of<VectorSeries, T>::value> > {
    static void setProperties(T &dataSeries, QCustomPlot &plot, QCPColorScale &)
    {
        /// @todo ALX
    }
};

/**
 * Default implementation of IAxisHelper, which takes data series to set axes properties
 * @tparam T the data series' type
 */
template <typename T>
struct AxisHelper : public IAxisHelper {
    explicit AxisHelper(T &dataSeries) : m_DataSeries{dataSeries} {}

    void setProperties(QCustomPlot &plot, QCPColorScale &colorScale) override
    {
        AxisSetter<T>::setProperties(m_DataSeries, plot, colorScale);
    }

    T &m_DataSeries;
};

} // namespace

std::unique_ptr<IAxisHelper>
IAxisHelperFactory::create(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    if (auto scalarSeries = std::dynamic_pointer_cast<ScalarSeries>(dataSeries)) {
        return std::make_unique<AxisHelper<ScalarSeries> >(*scalarSeries);
    }
    else if (auto vectorSeries = std::dynamic_pointer_cast<VectorSeries>(dataSeries)) {
        return std::make_unique<AxisHelper<VectorSeries> >(*vectorSeries);
    }
    else {
        return std::make_unique<AxisHelper<IDataSeries> >(*dataSeries);
    }
}
