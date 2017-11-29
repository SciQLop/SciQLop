#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/AxisRenderingUtils.h"
#include "Visualization/ColorScaleEditor.h"
#include "Visualization/PlottablesRenderingUtils.h"
#include "Visualization/SqpColorScale.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/qcustomplot.h"

#include <Common/DateUtils.h>

#include <Data/IDataSeries.h>

#include <SqpApplication.h>

namespace {

/// Name of the axes layer in QCustomPlot
const auto AXES_LAYER = QStringLiteral("axes");

/// Icon used to show x-axis properties
const auto HIDE_AXIS_ICON_PATH = QStringLiteral(":/icones/down.png");

/// Name of the overlay layer in QCustomPlot
const auto OVERLAY_LAYER = QStringLiteral("overlay");

/// Pixmap used to show x-axis properties
const auto SHOW_AXIS_ICON_PATH = QStringLiteral(":/icones/up.png");

/// Tooltip format for graphs
const auto GRAPH_TOOLTIP_FORMAT = QStringLiteral("key: %1\nvalue: %2");

/// Tooltip format for colormaps
const auto COLORMAP_TOOLTIP_FORMAT = QStringLiteral("x: %1\ny: %2\nvalue: %3");

/// Offset used to shift the tooltip of the mouse
const auto TOOLTIP_OFFSET = QPoint{20, 20};

/// Tooltip display rectangle (the tooltip is hidden when the mouse leaves this rectangle)
const auto TOOLTIP_RECT = QRect{10, 10, 10, 10};

/// Timeout after which the tooltip is displayed
const auto TOOLTIP_TIMEOUT = 500;

void initPointTracerStyle(QCPItemTracer &tracer) noexcept
{
    tracer.setInterpolating(false);
    tracer.setStyle(QCPItemTracer::tsCircle);
    tracer.setSize(3);
    tracer.setPen(QPen(Qt::black));
    tracer.setBrush(Qt::black);
    tracer.setSelectable(false);
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
    text.setSelectable(false);
}

/**
 * Returns the cell index (x or y) of a colormap according to the coordinate passed in parameter.
 * This method handles the fact that a colormap axis can be logarithmic or linear.
 * @param colormap the colormap for which to calculate the index
 * @param coord the coord to convert to cell index
 * @param xCoord calculates the x index if true, calculates y index if false
 * @return the cell index
 */
int colorMapCellIndex(const QCPColorMap &colormap, double coord, bool xCoord)
{
    // Determines the axis of the colormap according to xCoord, and whether it is logarithmic or not
    auto isLogarithmic = (xCoord ? colormap.keyAxis() : colormap.valueAxis())->scaleType()
                         == QCPAxis::stLogarithmic;

    if (isLogarithmic) {
        // For a logarithmic axis we can't use the conversion method of colormap, so we calculate
        // the index manually based on the position of the coordinate on the axis

        // Gets the axis range and the number of values between range bounds to calculate the step
        // between each value of the range
        auto range = xCoord ? colormap.data()->keyRange() : colormap.data()->valueRange();
        auto nbValues = (xCoord ? colormap.data()->keySize() : colormap.data()->valueSize()) - 1;
        auto valueStep
            = (std::log10(range.upper) - std::log10(range.lower)) / static_cast<double>(nbValues);

        // According to the coord position, calculates the closest index in the range
        return std::round((std::log10(coord) - std::log10(range.lower)) / valueStep);
    }
    else {
        // For a linear axis, we use the conversion method of colormap
        int index;
        if (xCoord) {
            colormap.data()->coordToCell(coord, 0., &index, nullptr);
        }
        else {
            colormap.data()->coordToCell(0., coord, nullptr, &index);
        }

        return index;
    }
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
              m_XAxisLabel{},
              m_ColorScale{SqpColorScale{m_Plot}}
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
    SqpColorScale m_ColorScale; /// Color scale used for some types of graphs (as spectrograms)
};

VisualizationGraphRenderingDelegate::VisualizationGraphRenderingDelegate(
    VisualizationGraphWidget &graphWidget)
        : impl{spimpl::make_unique_impl<VisualizationGraphRenderingDelegatePrivate>(graphWidget)}
{
}

void VisualizationGraphRenderingDelegate::onMouseDoubleClick(QMouseEvent *event) noexcept
{
    // Opens color scale editor if color scale is double clicked
    auto colorScale = static_cast<QCPColorScale *>(impl->m_Plot.layoutElementAt(event->pos()));
    if (impl->m_ColorScale.m_Scale == colorScale) {
        if (ColorScaleEditor{impl->m_ColorScale}.exec() == QDialog::Accepted) {
            impl->m_Plot.replot();
        }
    }
}

void VisualizationGraphRenderingDelegate::onMouseMove(QMouseEvent *event) noexcept
{
    // Cancels pending refresh
    impl->m_TracerTimer.disconnect();

    // Reinits tracers
    impl->m_PointTracer->setGraph(nullptr);
    impl->m_PointTracer->setVisible(false);
    impl->m_Plot.replot();

    QString tooltip{};

    // Gets the graph under the mouse position
    auto eventPos = event->pos();
    if (auto graph = qobject_cast<QCPGraph *>(impl->m_Plot.plottableAt(eventPos))) {
        auto mouseKey = graph->keyAxis()->pixelToCoord(eventPos.x());
        auto graphData = graph->data();

        // Gets the closest data point to the mouse
        auto graphDataIt = graphData->findBegin(mouseKey);
        if (graphDataIt != graphData->constEnd()) {
            // Sets tooltip
            auto key = formatValue(graphDataIt->key, *graph->keyAxis());
            auto value = formatValue(graphDataIt->value, *graph->valueAxis());
            tooltip = GRAPH_TOOLTIP_FORMAT.arg(key, value);

            // Displays point tracer
            impl->m_PointTracer->setGraph(graph);
            impl->m_PointTracer->setGraphKey(graphDataIt->key);
            impl->m_PointTracer->setLayer(
                impl->m_Plot.layer("main")); // Tracer is set on top of the plot's main layer
            impl->m_PointTracer->setVisible(true);
            impl->m_Plot.replot();
        }
    }
    else if (auto colorMap = qobject_cast<QCPColorMap *>(impl->m_Plot.plottableAt(eventPos))) {
        // Gets x and y coords
        auto x = colorMap->keyAxis()->pixelToCoord(eventPos.x());
        auto y = colorMap->valueAxis()->pixelToCoord(eventPos.y());

        // Calculates x and y cell indexes, and retrieves the underlying value
        auto xCellIndex = colorMapCellIndex(*colorMap, x, true);
        auto yCellIndex = colorMapCellIndex(*colorMap, y, false);
        auto value = colorMap->data()->cell(xCellIndex, yCellIndex);

        // Sets tooltips
        tooltip = COLORMAP_TOOLTIP_FORMAT.arg(formatValue(x, *colorMap->keyAxis()),
                                              formatValue(y, *colorMap->valueAxis()),
                                              formatValue(value, *colorMap->colorScale()->axis()));
    }

    if (!tooltip.isEmpty()) {
        // Starts timer to show tooltip after timeout
        auto showTooltip = [tooltip, eventPos, this]() {
            QToolTip::showText(impl->m_Plot.mapToGlobal(eventPos) + TOOLTIP_OFFSET, tooltip,
                               &impl->m_Plot, TOOLTIP_RECT);
        };

        QObject::connect(&impl->m_TracerTimer, &QTimer::timeout, showTooltip);
        impl->m_TracerTimer.start();
    }
}

void VisualizationGraphRenderingDelegate::onPlotUpdated() noexcept
{
    // Updates color scale bounds
    impl->m_ColorScale.updateDataRange();
    impl->m_Plot.replot();
}

void VisualizationGraphRenderingDelegate::setAxesProperties(
    std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    // Stores x-axis label to be able to retrieve it when x-axis pixmap is unselected
    impl->m_XAxisLabel = dataSeries->xAxisUnit().m_Name;

    auto axisHelper = IAxisHelperFactory::create(dataSeries);
    axisHelper->setProperties(impl->m_Plot, impl->m_ColorScale);

    // Updates x-axis state
    impl->updateXAxisState();

    impl->m_Plot.layer(AXES_LAYER)->replot();
}

void VisualizationGraphRenderingDelegate::setPlottablesProperties(
    std::shared_ptr<IDataSeries> dataSeries, PlottablesMap &plottables) noexcept
{
    auto plottablesHelper = IPlottablesHelperFactory::create(dataSeries);
    plottablesHelper->setProperties(plottables);
}

void VisualizationGraphRenderingDelegate::showGraphOverlay(bool show) noexcept
{
    auto overlay = impl->m_Plot.layer(OVERLAY_LAYER);
    overlay->setVisible(show);
    overlay->replot();
}
