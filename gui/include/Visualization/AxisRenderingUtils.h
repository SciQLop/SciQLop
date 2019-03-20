#ifndef SCIQLOP_AXISRENDERINGUTILS_H
#define SCIQLOP_AXISRENDERINGUTILS_H

#include <memory>

#include <QtCore/QLoggingCategory>
#include <QtCore/QString>

Q_DECLARE_LOGGING_CATEGORY(LOG_AxisRenderingUtils)

class IDataSeries;
class QCPAxis;
class QCustomPlot;
class SqpColorScale;
class Variable2;

/// Formats a data value according to the axis on which it is present
QString formatValue(double value, const QCPAxis& axis);

/**
 * Helper used to handle axes rendering
 */
struct IAxisHelper
{
    virtual ~IAxisHelper() noexcept = default;

    /// Set properties of the plot's axes and the color scale associated to plot passed as
    /// parameters
    /// @param plot the plot for which to set axe properties
    /// @param colorScale the color scale for which to set properties
    virtual void setProperties(QCustomPlot& plot, SqpColorScale& colorScale) = 0;

    /// Set the units of the plot's axes and the color scale associated to plot passed as
    /// parameters
    /// @param plot the plot for which to set axe units
    /// @param colorScale the color scale for which to set unit
    virtual void setUnits(QCustomPlot& plot, SqpColorScale& colorScale) = 0;
};

struct IAxisHelperFactory
{
    /// Creates IPlottablesHelper according to the type of data series a variable holds
    static std::unique_ptr<IAxisHelper> create(Variable2& variable) noexcept;
};

#endif // SCIQLOP_AXISRENDERINGUTILS_H
