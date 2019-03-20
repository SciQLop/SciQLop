#ifndef SCIQLOP_PLOTTABLESRENDERINGUTILS_H
#define SCIQLOP_PLOTTABLESRENDERINGUTILS_H

#include <Data/DataSeriesType.h>

#include <Visualization/VisualizationDefs.h>

#include <memory>

#include <QtCore/QLoggingCategory>

Q_DECLARE_LOGGING_CATEGORY(LOG_PlottablesRenderingUtils)

class QCPColorScale;
class QCustomPlot;
class Variable2;

/**
 * Helper used to handle plottables rendering
 */
struct IPlottablesHelper
{
    virtual ~IPlottablesHelper() noexcept = default;

    /// Set properties of the plottables passed as parameter
    /// @param plottables the plottables for which to set properties
    virtual void setProperties(PlottablesMap& plottables) = 0;
};

struct IPlottablesHelperFactory
{
    /// Creates IPlottablesHelper according to the type of data series a variable holds
    static std::unique_ptr<IPlottablesHelper> create(Variable2& variable) noexcept;
};

#endif // SCIQLOP_PLOTTABLESRENDERINGUTILS_H
