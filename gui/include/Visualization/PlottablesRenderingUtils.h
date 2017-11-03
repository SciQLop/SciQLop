#ifndef SCIQLOP_PLOTTABLESRENDERINGUTILS_H
#define SCIQLOP_PLOTTABLESRENDERINGUTILS_H

#include <Visualization/VisualizationDefs.h>

#include <memory>

class IDataSeries;
class QCPColorScale;
class QCustomPlot;

/**
 * Helper used to handle plottables rendering
 */
struct IPlottablesHelper {
    virtual ~IPlottablesHelper() noexcept = default;

    /// Set properties of the plottables passed as parameter
    /// @param plottables the plottables for which to set properties
    virtual void setProperties(PlottablesMap &plottables) = 0;
};

struct IPlottablesHelperFactory {
    /// Creates IPlottablesHelper according to a data series
    static std::unique_ptr<IPlottablesHelper>
    create(std::shared_ptr<IDataSeries> dataSeries) noexcept;
};

#endif // SCIQLOP_PLOTTABLESRENDERINGUTILS_H
