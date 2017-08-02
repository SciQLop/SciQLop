#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/qcustomplot.h"

namespace {

/// Timeout after which a tracer is displayed
const auto TRACER_TIMEOUT = 500;

} // namespace

struct VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegatePrivate {
    explicit VisualizationGraphRenderingDelegatePrivate(QCustomPlot &plot)
            : m_Plot{plot},
              m_PointTracer{new QCPItemTracer{&plot}},
              m_TextTracer{new QCPItemText{&plot}},
              m_TracerTimer{}
    {

        m_TracerTimer.setInterval(TRACER_TIMEOUT);
        m_TracerTimer.setSingleShot(true);
    }

    QCustomPlot &m_Plot;
    QCPItemTracer *m_PointTracer;
    QCPItemText *m_TextTracer;
    QTimer m_TracerTimer;
};

VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegate(QCustomPlot &plot)
        : impl{spimpl::make_unique_impl<VisualizationGraphRenderingDelegatePrivate>(plot)}
{
}

void VisualizationGraphRenderingDelegate::onMouseMove(QMouseEvent *event) noexcept
{
    // Cancels pending refresh
    impl->m_TracerTimer.disconnect();

    auto showTracers = [ eventPos = event->pos(), this ]()
    {
    };

    // Starts the timer to display tracers at timeout
    QObject::connect(&impl->m_TracerTimer, &QTimer::timeout, showTracers);
    impl->m_TracerTimer.start();
}
