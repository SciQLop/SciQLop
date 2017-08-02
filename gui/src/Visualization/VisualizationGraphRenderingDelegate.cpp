#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/qcustomplot.h"

namespace {

const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss:zzz");

const auto TEXT_TRACER_FORMAT = QStringLiteral("key: %1\nvalue: %2");

/// Timeout after which a tracer is displayed
const auto TRACER_TIMEOUT = 500;

/// Formats a data value according to the axis on which it is present
QString formatValue(double value, const QCPAxis &axis)
{
    // If the axis is a time axis, formats the value as a date
    return qSharedPointerDynamicCast<QCPAxisTickerDateTime>(axis.ticker())
               ? QCPAxisTickerDateTime::keyToDateTime(value).toString(DATETIME_FORMAT)
               : QString::number(value);
}
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
        // Reinits tracers
        impl->m_PointTracer->setGraph(nullptr);
        impl->m_PointTracer->setVisible(false);
        impl->m_TextTracer->setVisible(false);
        impl->m_Plot.replot();

        // Gets the graph under the mouse position
        if (auto graph = qobject_cast<QCPGraph *>(impl->m_Plot.plottableAt(eventPos))) {
            auto mouseKey = graph->keyAxis()->pixelToCoord(eventPos.x());
            auto graphData = graph->data();

            // Gets the closest data point to the mouse
            auto graphDataIt = graphData->findBegin(mouseKey);
            if (graphDataIt != graphData->constEnd()) {
                auto key = formatValue(graphDataIt->key, *graph->keyAxis());
                auto value = formatValue(graphDataIt->value, *graph->valueAxis());
                impl->m_TextTracer->setText(TEXT_TRACER_FORMAT.arg(key, value));
        }
    };

    // Starts the timer to display tracers at timeout
    QObject::connect(&impl->m_TracerTimer, &QTimer::timeout, showTracers);
    impl->m_TracerTimer.start();
}
