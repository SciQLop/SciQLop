#ifndef SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
#define SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H

#include <Common/spimpl.h>

class QCustomPlot;
class QMouseEvent;

class VisualizationGraphRenderingDelegate {
public:
    explicit VisualizationGraphRenderingDelegate(QCustomPlot &plot);

    void onMouseMove(QMouseEvent *event) noexcept;

private:
    class VisualizationGraphRenderingDelegatePrivate;
    spimpl::unique_impl_ptr<VisualizationGraphRenderingDelegatePrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHRENDERINGDELEGATE_H
