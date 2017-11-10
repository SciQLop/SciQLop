#ifndef SCIQLOP_AXISRENDERINGUTILS_H
#define SCIQLOP_AXISRENDERINGUTILS_H

#include <memory>

#include <QtCore/QString>

class IDataSeries;
class QCPAxis;
class QCPColorScale;
class QCustomPlot;

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
    virtual void setProperties(QCustomPlot &plot, QCPColorScale &colorScale) = 0;
};

struct IAxisHelperFactory {
    /// Creates IAxisHelper according to a data series
    static std::unique_ptr<IAxisHelper> create(std::shared_ptr<IDataSeries> dataSeries) noexcept;
};

#endif // SCIQLOP_AXISRENDERINGUTILS_H
