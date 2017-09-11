#ifndef SCIQLOP_QCUSTOMPLOTSYNCHRONIZER_H
#define SCIQLOP_QCUSTOMPLOTSYNCHRONIZER_H

#include "Visualization/IGraphSynchronizer.h"

#include <Common/spimpl.h>

/**
 * @brief The QCustomPlotSynchronizer class is an implementation of IGraphSynchronizer that handles
 * graphs using QCustomPlot elements
 * @sa IGraphSynchronizer
 * @sa QCustomPlot
 */
class QCustomPlotSynchronizer : public IGraphSynchronizer {
public:
    explicit QCustomPlotSynchronizer();

    /// @sa IGraphSynchronizer::addGraph()
    virtual void addGraph(VisualizationGraphWidget &graph) const override;

private:
    class QCustomPlotSynchronizerPrivate;
    spimpl::unique_impl_ptr<QCustomPlotSynchronizerPrivate> impl;
};

#endif // SCIQLOP_QCUSTOMPLOTSYNCHRONIZER_H
