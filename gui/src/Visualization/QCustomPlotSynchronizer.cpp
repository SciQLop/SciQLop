#include "Visualization/QCustomPlotSynchronizer.h"

#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/qcustomplot.h"

struct QCustomPlotSynchronizer::QCustomPlotSynchronizerPrivate {
    explicit QCustomPlotSynchronizerPrivate()
            : m_MarginGroup{std::make_unique<QCPMarginGroup>(nullptr)}
    {
    }

    /// Sets the same margin sides for all added plot elements
    std::unique_ptr<QCPMarginGroup> m_MarginGroup;
};

QCustomPlotSynchronizer::QCustomPlotSynchronizer()
        : impl{spimpl::make_unique_impl<QCustomPlotSynchronizerPrivate>()}
{
}

void QCustomPlotSynchronizer::addGraph(VisualizationGraphWidget &graph) const
{
    // Adds all plot elements of the graph to the margin group: all these elements will then have
    // the same margin sides
    auto &plot = graph.plot();
    for (auto axisRect : plot.axisRects()) {
        // Sames margin sides at left and right
        axisRect->setMarginGroup(QCP::msLeft | QCP::msRight, impl->m_MarginGroup.get());
    }
}
