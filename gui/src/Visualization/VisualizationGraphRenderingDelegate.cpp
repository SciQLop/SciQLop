#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/qcustomplot.h"

#include <Common/DateUtils.h>

#include <Data/IDataSeries.h>

#include <SqpApplication.h>

namespace {

/// Name of the axes layer in QCustomPlot
const auto AXES_LAYER = QStringLiteral("axes");

const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss:zzz");

/// Format for datetimes on a axis
const auto DATETIME_TICKER_FORMAT = QStringLiteral("yyyy/MM/dd \nhh:mm:ss");

/// Icon used to show x-axis properties
const auto HIDE_AXIS_ICON_PATH = QStringLiteral(":/icones/down.png");

/// Name of the overlay layer in QCustomPlot
const auto OVERLAY_LAYER = QStringLiteral("overlay");

/// Pixmap used to show x-axis properties
const auto SHOW_AXIS_ICON_PATH = QStringLiteral(":/icones/up.png");

const auto TOOLTIP_FORMAT = QStringLiteral("key: %1\nvalue: %2");

/// Offset used to shift the tooltip of the mouse
const auto TOOLTIP_OFFSET = QPoint{20, 20};

/// Tooltip display rectangle (the tooltip is hidden when the mouse leaves this rectangle)
const auto TOOLTIP_RECT = QRect{10, 10, 10, 10};

/// Timeout after which the tooltip is displayed
const auto TOOLTIP_TIMEOUT = 500;

/// Generates the appropriate ticker for an axis, depending on whether the axis displays time or
/// non-time data
QSharedPointer<QCPAxisTicker> axisTicker(bool isTimeAxis)
{
    if (isTimeAxis) {
        auto dateTicker = QSharedPointer<QCPAxisTickerDateTime>::create();
        dateTicker->setDateTimeFormat(DATETIME_TICKER_FORMAT);
        dateTicker->setDateTimeSpec(Qt::UTC);

        return dateTicker;
    }
    else {
        // default ticker
        return QSharedPointer<QCPAxisTicker>::create();
    }
}

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

QPixmap pixmap(const QString &iconPath) noexcept
{
    return QIcon{iconPath}.pixmap(QSize{16, 16});
}

void initClosePixmapStyle(QCPItemPixmap &pixmap) noexcept
{
    // Icon
    pixmap.setPixmap(
        sqpApp->style()->standardIcon(QStyle::SP_TitleBarCloseButton).pixmap(QSize{16, 16}));

    // Position
    pixmap.topLeft->setType(QCPItemPosition::ptAxisRectRatio);
    pixmap.topLeft->setCoords(1, 0);
    pixmap.setClipToAxisRect(false);

    // Can be selected
    pixmap.setSelectable(true);
}

void initXAxisPixmapStyle(QCPItemPixmap &itemPixmap) noexcept
{
    // Icon
    itemPixmap.setPixmap(pixmap(HIDE_AXIS_ICON_PATH));

    // Position
    itemPixmap.topLeft->setType(QCPItemPosition::ptAxisRectRatio);
    itemPixmap.topLeft->setCoords(0, 1);
    itemPixmap.setClipToAxisRect(false);

    // Can be selected
    itemPixmap.setSelectable(true);
}

void initTitleTextStyle(QCPItemText &text) noexcept
{
    // Font and background styles
    text.setColor(Qt::gray);
    text.setBrush(Qt::white);

    // Position
    text.setPositionAlignment(Qt::AlignTop | Qt::AlignLeft);
    text.position->setType(QCPItemPosition::ptAxisRectRatio);
    text.position->setCoords(0.5, 0);
}

} // namespace

struct VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegatePrivate {
    explicit VisualizationGraphRenderingDelegatePrivate(VisualizationGraphWidget &graphWidget)
            : m_Plot{graphWidget.plot()},
              m_PointTracer{new QCPItemTracer{&m_Plot}},
              m_TracerTimer{},
              m_ClosePixmap{new QCPItemPixmap{&m_Plot}},
              m_TitleText{new QCPItemText{&m_Plot}},
              m_XAxisPixmap{new QCPItemPixmap{&m_Plot}},
              m_ShowXAxis{true},
              m_XAxisLabel{}
    {
        initPointTracerStyle(*m_PointTracer);

        m_TracerTimer.setInterval(TOOLTIP_TIMEOUT);
        m_TracerTimer.setSingleShot(true);

        // Inits "close button" in plot overlay
        m_ClosePixmap->setLayer(OVERLAY_LAYER);
        initClosePixmapStyle(*m_ClosePixmap);

        // Connects pixmap selection to graph widget closing
        QObject::connect(m_ClosePixmap, &QCPItemPixmap::selectionChanged,
                         [&graphWidget](bool selected) {
                             if (selected) {
                                 graphWidget.close();
                             }
                         });

        // Inits graph name in plot overlay
        m_TitleText->setLayer(OVERLAY_LAYER);
        m_TitleText->setText(graphWidget.name());
        initTitleTextStyle(*m_TitleText);

        // Inits "show x-axis button" in plot overlay
        m_XAxisPixmap->setLayer(OVERLAY_LAYER);
        initXAxisPixmapStyle(*m_XAxisPixmap);

        // Connects pixmap selection to graph x-axis showing/hiding
        QObject::connect(m_XAxisPixmap, &QCPItemPixmap::selectionChanged, [this]() {
            if (m_XAxisPixmap->selected()) {
                // Changes the selection state and refreshes the x-axis
                m_ShowXAxis = !m_ShowXAxis;
                updateXAxisState();
                m_Plot.layer(AXES_LAYER)->replot();

                // Deselects the x-axis pixmap and updates icon
                m_XAxisPixmap->setSelected(false);
                m_XAxisPixmap->setPixmap(
                    pixmap(m_ShowXAxis ? HIDE_AXIS_ICON_PATH : SHOW_AXIS_ICON_PATH));
                m_Plot.layer(OVERLAY_LAYER)->replot();
            }
        });
    }

    /// Updates state of x-axis according to the current selection of x-axis pixmap
    /// @remarks the method doesn't call plot refresh
    void updateXAxisState() noexcept
    {
        m_Plot.xAxis->setTickLabels(m_ShowXAxis);
        m_Plot.xAxis->setLabel(m_ShowXAxis ? m_XAxisLabel : QString{});
    }

    QCustomPlot &m_Plot;
    QCPItemTracer *m_PointTracer;
    QTimer m_TracerTimer;
    QCPItemPixmap *m_ClosePixmap; /// Graph's close button
    QCPItemText *m_TitleText;     /// Graph's title
    QCPItemPixmap *m_XAxisPixmap;
    bool m_ShowXAxis; /// X-axis properties are shown or hidden
    QString m_XAxisLabel;
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

void VisualizationGraphRenderingDelegate::setAxesProperties(const Unit &xAxisUnit,
                                                            const Unit &valuesUnit) noexcept
{
    // Stores x-axis label to be able to retrieve it when x-axis pixmap is unselected
    impl->m_XAxisLabel = xAxisUnit.m_Name;

    auto setAxisProperties = [](auto axis, const auto &unit) {
        // label (unit name)
        axis->setLabel(unit.m_Name);

        // ticker (depending on the type of unit)
        axis->setTicker(axisTicker(unit.m_TimeUnit));
    };
    setAxisProperties(impl->m_Plot.xAxis, xAxisUnit);
    setAxisProperties(impl->m_Plot.yAxis, valuesUnit);

    // Updates x-axis state
    impl->updateXAxisState();

    impl->m_Plot.layer(AXES_LAYER)->replot();
}

void VisualizationGraphRenderingDelegate::showGraphOverlay(bool show) noexcept
{
    auto overlay = impl->m_Plot.layer(OVERLAY_LAYER);
    overlay->setVisible(show);
    overlay->replot();
}
