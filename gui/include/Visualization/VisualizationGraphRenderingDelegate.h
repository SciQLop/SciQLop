#ifndef SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
#define SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H

#include <Common/spimpl.h>

class QCustomPlot;
class QMouseEvent;
class VisualizationGraphWidget;

class VisualizationGraphRenderingDelegate {
public:
    /// Ctor
    /// @param graphWidget the graph widget to which the delegate is associated
    /// @remarks the graph widget must exist throughout the life cycle of the delegate
    explicit VisualizationGraphRenderingDelegate(VisualizationGraphWidget &graphWidget);

    void onMouseMove(QMouseEvent *event) noexcept;

private:
    class VisualizationGraphRenderingDelegatePrivate;
    spimpl::unique_impl_ptr<VisualizationGraphRenderingDelegatePrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
