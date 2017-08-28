#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/qcustomplot.h"

#include <Common/DateUtils.h>

namespace {

const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss:zzz");

const auto TOOLTIP_FORMAT = QStringLiteral("key: %1\nvalue: %2");

/// Offset used to shift the tooltip of the mouse
const auto TOOLTIP_OFFSET = QPoint{20, 20};

/// Tooltip display rectangle (the tooltip is hidden when the mouse leaves this rectangle)
const auto TOOLTIP_RECT = QRect{10, 10, 10, 10};

/// Timeout after which the tooltip is displayed
const auto TOOLTIP_TIMEOUT = 500;

/// Formats a data value according to the axis on which it is present
QString formatValue(double value, const QCPAxis &axis)
{
    // If the axis is a time axis, formats the value as a date
    if (auto axisTicker = qSharedPointerDynamicCast<QCPAxisTickerDateTime>(axis.ticker())) {
        return DateUtils::dateTime(value, axisTicker->dateTimeSpec()).toString(DATETIME_FORMAT);
    }
    else {
        return QString::number(value);
    }
}

void initPointTracerStyle(QCPItemTracer &tracer) noexcept
{
    tracer.setInterpolating(false);
    tracer.setStyle(QCPItemTracer::tsCircle);
    tracer.setSize(3);
    tracer.setPen(QPen(Qt::black));
    tracer.setBrush(Qt::black);
}

} // namespace

struct VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegatePrivate {
    explicit VisualizationGraphRenderingDelegatePrivate(VisualizationGraphWidget &graphWidget)
            : m_Plot{graphWidget.plot()},
              m_PointTracer{new QCPItemTracer{&m_Plot}},
              m_TracerTimer{},
    {
        initPointTracerStyle(*m_PointTracer);

        m_TracerTimer.setInterval(TOOLTIP_TIMEOUT);
        m_TracerTimer.setSingleShot(true);
    }

    QCustomPlot &m_Plot;
    QCPItemTracer *m_PointTracer;
    QTimer m_TracerTimer;
};

VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegate(
    VisualizationGraphWidget &graphWidget)
        : impl{spimpl::make_unique_impl<VisualizationGraphRenderingDelegatePrivate>(graphWidget)}
{
}

void VisualizationGraphRenderingDelegate::onMouseMove(QMouseEvent *event) noexcept
{
    // Cancels pending refresh
    impl->m_TracerTimer.disconnect();

    // Reinits tracers
    impl->m_PointTracer->setGraph(nullptr);
    impl->m_PointTracer->setVisible(false);
    impl->m_Plot.replot();

    // Gets the graph under the mouse position
    auto eventPos = event->pos();
    if (auto graph = qobject_cast<QCPGraph *>(impl->m_Plot.plottableAt(eventPos))) {
        auto mouseKey = graph->keyAxis()->pixelToCoord(eventPos.x());
        auto graphData = graph->data();

        // Gets the closest data point to the mouse
        auto graphDataIt = graphData->findBegin(mouseKey);
        if (graphDataIt != graphData->constEnd()) {
            auto key = formatValue(graphDataIt->key, *graph->keyAxis());
            auto value = formatValue(graphDataIt->value, *graph->valueAxis());

            // Displays point tracer
            impl->m_PointTracer->setGraph(graph);
            impl->m_PointTracer->setGraphKey(graphDataIt->key);
            impl->m_PointTracer->setLayer(
                impl->m_Plot.layer("main")); // Tracer is set on top of the plot's main layer
            impl->m_PointTracer->setVisible(true);
            impl->m_Plot.replot();

            // Starts timer to show tooltip after timeout
            auto showTooltip = [ tooltip = TOOLTIP_FORMAT.arg(key, value), eventPos, this ]()
            {
                QToolTip::showText(impl->m_Plot.mapToGlobal(eventPos) + TOOLTIP_OFFSET, tooltip,
                                   &impl->m_Plot, TOOLTIP_RECT);
            };

            QObject::connect(&impl->m_TracerTimer, &QTimer::timeout, showTooltip);
            impl->m_TracerTimer.start();
        }
    }
}
