#ifndef SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
#define SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H

#include <Common/spimpl.h>

#include <Visualization/VisualizationDefs.h>

class IDataSeries;
class QCustomPlot;
class QMouseEvent;
class Unit;
class VisualizationGraphWidget;

class VisualizationGraphRenderingDelegate {
public:
    /// Ctor
    /// @param graphWidget the graph widget to which the delegate is associated
    /// @remarks the graph widget must exist throughout the life cycle of the delegate
    explicit VisualizationGraphRenderingDelegate(VisualizationGraphWidget &graphWidget);

    void onMouseMove(QMouseEvent *event) noexcept;

    /// Sets properties of the plot's axes from the data series passed as parameter
    void setAxesProperties(std::shared_ptr<IDataSeries> dataSeries) noexcept;


    /// Shows or hides graph overlay (name, close button, etc.)
    void showGraphOverlay(bool show) noexcept;

private:
    class VisualizationGraphRenderingDelegatePrivate;
    spimpl::unique_impl_ptr<VisualizationGraphRenderingDelegatePrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
