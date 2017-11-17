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

/// Formats a data value according to the axis on which it is present
QString formatValue(double value, const QCPAxis &axis);

/**
 * Helper used to handle axes rendering
 */
struct IAxisHelper {
    virtual ~IAxisHelper() noexcept = default;

    /// Set properties of the plot's axes and the color scale associated to plot passed as
    /// parameters
    /// @param plot the plot for which to set axe properties
    /// @param colorScale the color scale for which to set properties
    virtual void setProperties(QCustomPlot &plot, SqpColorScale &colorScale) = 0;
};

struct IAxisHelperFactory {
    /// Creates IAxisHelper according to a data series
    static std::unique_ptr<IAxisHelper> create(std::shared_ptr<IDataSeries> dataSeries) noexcept;
};

#endif // SCIQLOP_AXISRENDERINGUTILS_H
