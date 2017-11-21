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

    void onMouseDoubleClick(QMouseEvent *event) noexcept;
    void onMouseMove(QMouseEvent *event) noexcept;
    /// Updates rendering when data of plot changed
    void onPlotUpdated() noexcept;

    /// Sets properties of the plot's axes from the data series passed as parameter
    void setAxesProperties(std::shared_ptr<IDataSeries> dataSeries) noexcept;

    /// Sets rendering properties of the plottables passed as parameter, from the data series that
    /// generated these
    void setPlottablesProperties(std::shared_ptr<IDataSeries> dataSeries,
                                 PlottablesMap &plottables) noexcept;

    /// Shows or hides graph overlay (name, close button, etc.)
    void showGraphOverlay(bool show) noexcept;

private:
    class VisualizationGraphRenderingDelegatePrivate;
    spimpl::unique_impl_ptr<VisualizationGraphRenderingDelegatePrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
