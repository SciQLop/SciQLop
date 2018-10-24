#ifndef SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
#define SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H

#include <Common/spimpl.h>

#include <Visualization/VisualizationDefs.h>

class IDataSeries;
class QCustomPlot;
class QMouseEvent;
class Unit;
class Variable;
class VisualizationGraphWidget;

class VisualizationGraphRenderingDelegate {
public:
    /// Ctor
    /// @param graphWidget the graph widget to which the delegate is associated
    /// @remarks the graph widget must exist throughout the life cycle of the delegate
    explicit VisualizationGraphRenderingDelegate(VisualizationGraphWidget &graphWidget);

    void onMouseDoubleClick(QMouseEvent *event) noexcept;
    void updateTooltip(QMouseEvent *event) noexcept;
    /// Updates rendering when data of plot changed
    void onPlotUpdated() noexcept;

    /// Sets units of the plot's axes according to the properties of the variable passed as
    /// parameter
    void setAxesUnits(const Variable &variable) noexcept;

    /// Sets graph properties of the plottables passed as parameter, from the variable that
    /// generated these
    void setGraphProperties(const Variable &variable, PlottablesMap &plottables) noexcept;


    /// Shows or hides graph overlay (name, close button, etc.)
    void showGraphOverlay(bool show) noexcept;

private:
    class VisualizationGraphRenderingDelegatePrivate;
    spimpl::unique_impl_ptr<VisualizationGraphRenderingDelegatePrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
