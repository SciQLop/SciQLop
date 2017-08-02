#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/qcustomplot.h"

struct VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegatePrivate {
    explicit VisualizationGraphRenderingDelegatePrivate(QCustomPlot &plot) : m_Plot{plot} {}

    QCustomPlot &m_Plot;
};

VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegate(QCustomPlot &plot)
        : impl{spimpl::make_unique_impl<VisualizationGraphRenderingDelegatePrivate>(plot)}
{
}
