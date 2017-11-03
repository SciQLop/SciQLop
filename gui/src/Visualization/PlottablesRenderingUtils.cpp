#include "Visualization/PlottablesRenderingUtils.h"

#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>

#include <Visualization/qcustomplot.h>

namespace {

/**
 * Delegate used to set plottables properties
 */
template <typename T, typename Enabled = void>
struct PlottablesSetter {
    static void setProperties(T &, PlottablesMap &)
    {
        // Default implementation does nothing
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
        /// @todo ALX
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
    else if (auto vectorSeries = std::dynamic_pointer_cast<VectorSeries>(dataSeries)) {
        return std::make_unique<PlottablesHelper<VectorSeries> >(*vectorSeries);
    }
    else {
        return std::make_unique<PlottablesHelper<IDataSeries> >(*dataSeries);
    }
}
