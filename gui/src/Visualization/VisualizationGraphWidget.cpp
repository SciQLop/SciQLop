#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationCursorItem.h"
#include "Visualization/VisualizationDefs.h"
#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/VisualizationMultiZoneSelectionDialog.h"
#include "Visualization/VisualizationSelectionZoneItem.h"
#include "Visualization/VisualizationSelectionZoneManager.h"
#include "Visualization/VisualizationWidget.h"
#include "Visualization/VisualizationZoneWidget.h"
#include "ui_VisualizationGraphWidget.h"

#include <Actions/ActionsGuiController.h>
#include <Actions/FilteringAction.h>
#include <Common/MimeTypesDef.h>
#include <Common/containers.h>
#include <Data/DateTimeRangeHelper.h>
#include <DragAndDrop/DragDropGuiController.h>
#include <Settings/SqpSettingsDefs.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/Variable2.h>
#include <Variable/VariableController2.h>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphWidget, "VisualizationGraphWidget")

namespace
{

/// Key pressed to enable drag&drop in all modes
const auto DRAG_DROP_MODIFIER = Qt::AltModifier;

/// Key pressed to enable zoom on horizontal axis
const auto HORIZONTAL_ZOOM_MODIFIER = Qt::ControlModifier;

/// Key pressed to enable zoom on vertical axis
const auto VERTICAL_ZOOM_MODIFIER = Qt::ShiftModifier;

/// Speed of a step of a wheel event for a pan, in percentage of the axis range
const auto PAN_SPEED = 5;

/// Key pressed to enable a calibration pan
const auto VERTICAL_PAN_MODIFIER = Qt::AltModifier;

/// Key pressed to enable multi selection of selection zones
const auto MULTI_ZONE_SELECTION_MODIFIER = Qt::ControlModifier;

/// Minimum size for the zoom box, in percentage of the axis range
const auto ZOOM_BOX_MIN_SIZE = 0.8;

/// Format of the dates appearing in the label of a cursor
const auto CURSOR_LABELS_DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd\nhh:mm:ss:zzz");

} // namespace

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate
{

    explicit VisualizationGraphWidgetPrivate(const QString& name)
            : m_Name { name }
            , m_Flags { GraphFlag::EnableAll }
            , m_IsCalibration { false }
            , m_RenderingDelegate { nullptr }
    {
        m_plot = new QCustomPlot();
        // Necessary for all platform since Qt::AA_EnableHighDpiScaling is enable.
        m_plot->setPlottingHint(QCP::phFastPolylines, true);
    }

    void updateData(
        PlottablesMap& plottables, std::shared_ptr<Variable2> variable, const DateTimeRange& range)
    {
        VisualizationGraphHelper::updateData(plottables, variable, range);

        // Prevents that data has changed to update rendering
        m_RenderingDelegate->onPlotUpdated();
    }

    QString m_Name;
    // 1 variable -> n qcpplot
    std::map<std::shared_ptr<Variable2>, PlottablesMap> m_VariableToPlotMultiMap;
    GraphFlags m_Flags;
    bool m_IsCalibration;
    QCustomPlot* m_plot;
    QPoint m_lastMousePos;
    QCPRange m_lastXRange;
    QCPRange m_lastYRange;
    /// Delegate used to attach rendering features to the plot
    std::unique_ptr<VisualizationGraphRenderingDelegate> m_RenderingDelegate;

    QCPItemRect* m_DrawingZoomRect = nullptr;
    QStack<QPair<QCPRange, QCPRange>> m_ZoomStack;

    std::unique_ptr<VisualizationCursorItem> m_HorizontalCursor = nullptr;
    std::unique_ptr<VisualizationCursorItem> m_VerticalCursor = nullptr;

    VisualizationSelectionZoneItem* m_DrawingZone = nullptr;
    VisualizationSelectionZoneItem* m_HoveredZone = nullptr;
    QVector<VisualizationSelectionZoneItem*> m_SelectionZones;

    bool m_HasMovedMouse = false; // Indicates if the mouse moved in a releaseMouse even

    bool m_VariableAutoRangeOnInit = true;

    inline void enterPlotDrag(const QPoint& position)
    {
        m_lastMousePos = m_plot->mapFromParent(position);
        m_lastXRange = m_plot->xAxis->range();
        m_lastYRange = m_plot->yAxis->range();
    }

    inline bool isDrawingZoomRect() { return m_DrawingZoomRect != nullptr; }
    void updateZoomRect(const QPoint& newPos)
    {
        QPointF pos { m_plot->xAxis->pixelToCoord(newPos.x()),
            m_plot->yAxis->pixelToCoord(newPos.y()) };
        m_DrawingZoomRect->bottomRight->setCoords(pos);
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void applyZoomRect()
    {
        auto axisX = m_plot->axisRect()->axis(QCPAxis::atBottom);
        auto axisY = m_plot->axisRect()->axis(QCPAxis::atLeft);

        auto newAxisXRange = QCPRange { m_DrawingZoomRect->topLeft->coords().x(),
            m_DrawingZoomRect->bottomRight->coords().x() };

        auto newAxisYRange = QCPRange { m_DrawingZoomRect->topLeft->coords().y(),
            m_DrawingZoomRect->bottomRight->coords().y() };

        removeDrawingRect();

        if (newAxisXRange.size() > axisX->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)
            && newAxisYRange.size() > axisY->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0))
        {
            m_ZoomStack.push(qMakePair(axisX->range(), axisY->range()));
            axisX->setRange(newAxisXRange);
            axisY->setRange(newAxisYRange);

            m_plot->replot(QCustomPlot::rpQueuedReplot);
        }
    }

    inline bool isDrawingZoneRect() { return m_DrawingZone != nullptr; }
    void updateZoneRect(const QPoint& newPos)
    {
        m_DrawingZone->setEnd(m_plot->xAxis->pixelToCoord(newPos.x()));
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void startDrawingRect(const QPoint& pos)
    {
        removeDrawingRect();

        auto axisPos = posToAxisPos(pos);

        m_DrawingZoomRect = new QCPItemRect { m_plot };
        QPen p;
        p.setWidth(2);
        m_DrawingZoomRect->setPen(p);

        m_DrawingZoomRect->topLeft->setCoords(axisPos);
        m_DrawingZoomRect->bottomRight->setCoords(axisPos);
    }

    void removeDrawingRect()
    {
        if (m_DrawingZoomRect)
        {
            m_plot->removeItem(m_DrawingZoomRect); // the item is deleted by QCustomPlot
            m_DrawingZoomRect = nullptr;
            m_plot->replot(QCustomPlot::rpQueuedReplot);
        }
    }

    void selectZone(const QPoint& pos)
    {
        auto zoneAtPos = selectionZoneAt(pos);
        setSelectionZonesEditionEnabled(
            sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones);
    }

    void startDrawingZone(const QPoint& pos)
    {
        endDrawingZone();

        auto axisPos = posToAxisPos(pos);

        m_DrawingZone = new VisualizationSelectionZoneItem { m_plot };
        m_DrawingZone->setRange(axisPos.x(), axisPos.x());
        m_DrawingZone->setEditionEnabled(false);
    }

    void endDrawingZone()
    {
        if (m_DrawingZone)
        {
            auto drawingZoneRange = m_DrawingZone->range();
            if (qAbs(drawingZoneRange.m_TEnd - drawingZoneRange.m_TStart) > 0)
            {
                m_DrawingZone->setEditionEnabled(true);
                addSelectionZone(m_DrawingZone);
            }
            else
            {
                m_plot->removeItem(m_DrawingZone);
            }

            m_plot->replot(QCustomPlot::rpQueuedReplot);
            m_DrawingZone = nullptr;
        }
    }

    void moveSelectionZone(const QPoint& destination)
    {
        /*
         * I give up on this for now
         * @TODO implement this, the difficulty is that selection zones have their own
         * event handling code which seems to rely on QCP GUI event handling propagation
         * which was a realy bad design choice.
         */
    }

    void setSelectionZonesEditionEnabled(bool value)
    {
        for (auto s : m_SelectionZones)
        {
            s->setEditionEnabled(value);
        }
    }

    void addSelectionZone(VisualizationSelectionZoneItem* zone) { m_SelectionZones << zone; }

    VisualizationSelectionZoneItem* selectionZoneAt(const QPoint& pos) const
    {
        VisualizationSelectionZoneItem* selectionZoneItemUnderCursor = nullptr;
        auto minDistanceToZone = -1;
        for (auto zone : m_SelectionZones)
        {
            auto distanceToZone = zone->selectTest(pos, false);
            if ((minDistanceToZone < 0 || distanceToZone <= minDistanceToZone)
                && distanceToZone >= 0 && distanceToZone < m_plot->selectionTolerance())
            {
                selectionZoneItemUnderCursor = zone;
            }
        }

        return selectionZoneItemUnderCursor;
    }

    QVector<VisualizationSelectionZoneItem*> selectionZonesAt(
        const QPoint& pos, const QCustomPlot& plot) const
    {
        QVector<VisualizationSelectionZoneItem*> zones;
        for (auto zone : m_SelectionZones)
        {
            auto distanceToZone = zone->selectTest(pos, false);
            if (distanceToZone >= 0 && distanceToZone < plot.selectionTolerance())
            {
                zones << zone;
            }
        }

        return zones;
    }

    void moveSelectionZoneOnTop(VisualizationSelectionZoneItem* zone, QCustomPlot& plot)
    {
        if (!m_SelectionZones.isEmpty() && m_SelectionZones.last() != zone)
        {
            zone->moveToTop();
            m_SelectionZones.removeAll(zone);
            m_SelectionZones.append(zone);
        }
    }

    QPointF posToAxisPos(const QPoint& pos) const
    {
        auto axisX = m_plot->axisRect()->axis(QCPAxis::atBottom);
        auto axisY = m_plot->axisRect()->axis(QCPAxis::atLeft);
        return QPointF { axisX->pixelToCoord(pos.x()), axisY->pixelToCoord(pos.y()) };
    }

    bool pointIsInAxisRect(const QPointF& axisPoint, QCustomPlot& plot) const
    {
        auto axisX = plot.axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot.axisRect()->axis(QCPAxis::atLeft);
        return axisX->range().contains(axisPoint.x()) && axisY->range().contains(axisPoint.y());
    }

    inline QCPRange _pixDistanceToRange(double pos1, double pos2, QCPAxis* axis)
    {
        if (axis->scaleType() == QCPAxis::stLinear)
        {
            auto diff = axis->pixelToCoord(pos1) - axis->pixelToCoord(pos2);
            return QCPRange { axis->range().lower + diff, axis->range().upper + diff };
        }
        else
        {
            auto diff = axis->pixelToCoord(pos1) / axis->pixelToCoord(pos2);
            return QCPRange { axis->range().lower * diff, axis->range().upper * diff };
        }
    }

    void setRange(const DateTimeRange& newRange, bool updateVar = true)
    {
        this->m_plot->xAxis->setRange(newRange.m_TStart, newRange.m_TEnd);
        if (updateVar)
        {
            for (auto it = m_VariableToPlotMultiMap.begin(), end = m_VariableToPlotMultiMap.end();
                 it != end; it = m_VariableToPlotMultiMap.upper_bound(it->first))
            {
                sqpApp->variableController().asyncChangeRange(it->first, newRange);
            }
        }
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void setRange(const QCPRange& newRange)
    {
        auto graphRange = DateTimeRange { newRange.lower, newRange.upper };
        setRange(graphRange);
    }

    void rescaleY() { m_plot->yAxis->rescale(true); }

    std::tuple<double, double> moveGraph(const QPoint& destination)
    {
        auto currentPos = m_plot->mapFromParent(destination);
        auto xAxis = m_plot->axisRect()->rangeDragAxis(Qt::Horizontal);
        auto yAxis = m_plot->axisRect()->rangeDragAxis(Qt::Vertical);
        auto oldXRange = xAxis->range();
        auto oldYRange = yAxis->range();
        double dx = xAxis->pixelToCoord(m_lastMousePos.x()) - xAxis->pixelToCoord(currentPos.x());
        xAxis->setRange(m_lastXRange.lower + dx, m_lastXRange.upper + dx);
        if (yAxis->scaleType() == QCPAxis::stLinear)
        {
            double dy
                = yAxis->pixelToCoord(m_lastMousePos.y()) - yAxis->pixelToCoord(currentPos.y());
            yAxis->setRange(m_lastYRange.lower + dy, m_lastYRange.upper + dy);
        }
        else
        {
            double dy
                = yAxis->pixelToCoord(m_lastMousePos.y()) / yAxis->pixelToCoord(currentPos.y());
            yAxis->setRange(m_lastYRange.lower * dy, m_lastYRange.upper * dy);
        }
        auto newXRange = xAxis->range();
        auto newYRange = yAxis->range();
        setRange(xAxis->range());
        // m_lastMousePos = currentPos;
        return { newXRange.lower - oldXRange.lower, newYRange.lower - oldYRange.lower };
    }

    void zoom(double factor, int center, Qt::Orientation orientation)
    {
        QCPAxis* axis = m_plot->axisRect()->rangeZoomAxis(orientation);
        axis->scaleRange(factor, axis->pixelToCoord(center));
        if (orientation == Qt::Horizontal)
            setRange(axis->range());
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void transform(const DateTimeRangeTransformation& tranformation)
    {
        auto graphRange = m_plot->xAxis->range();
        DateTimeRange range { graphRange.lower, graphRange.upper };
        range = range.transform(tranformation);
        setRange(range);
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void move(double dx, double dy)
    {
        auto xAxis = m_plot->axisRect()->rangeDragAxis(Qt::Horizontal);
        auto yAxis = m_plot->axisRect()->rangeDragAxis(Qt::Vertical);
        xAxis->setRange(QCPRange(xAxis->range().lower + dx, xAxis->range().upper + dx));
        yAxis->setRange(QCPRange(yAxis->range().lower + dy, yAxis->range().upper + dy));
        setRange(xAxis->range());
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }

    void move(double factor, Qt::Orientation orientation)
    {
        auto oldRange = m_plot->xAxis->range();
        QCPAxis* axis = m_plot->axisRect()->rangeDragAxis(orientation);
        if (m_plot->xAxis->scaleType() == QCPAxis::stLinear)
        {
            double rg = (axis->range().upper - axis->range().lower) * (factor / 10);
            axis->setRange(axis->range().lower + (rg), axis->range().upper + (rg));
        }
        else if (m_plot->xAxis->scaleType() == QCPAxis::stLogarithmic)
        {
            int start = 0, stop = 0;
            double diff = 0.;
            if (factor > 0.0)
            {
                stop = m_plot->width() * factor / 10;
                start = 2 * m_plot->width() * factor / 10;
            }
            if (factor < 0.0)
            {
                factor *= -1.0;
                start = m_plot->width() * factor / 10;
                stop = 2 * m_plot->width() * factor / 10;
            }
            diff = axis->pixelToCoord(start) / axis->pixelToCoord(stop);
            axis->setRange(m_plot->axisRect()->rangeDragAxis(orientation)->range().lower * diff,
                m_plot->axisRect()->rangeDragAxis(orientation)->range().upper * diff);
        }
        if (orientation == Qt::Horizontal)
            setRange(axis->range());
        m_plot->replot(QCustomPlot::rpQueuedReplot);
    }
};

VisualizationGraphWidget::VisualizationGraphWidget(const QString& name, QWidget* parent)
        : VisualizationDragWidget { parent }
        , ui { new Ui::VisualizationGraphWidget }
        , impl { spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>(name) }
{
    ui->setupUi(this);
    this->layout()->addWidget(impl->m_plot);
    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);

    // The delegate must be initialized after the ui as it uses the plot
    impl->m_RenderingDelegate = std::make_unique<VisualizationGraphRenderingDelegate>(*this);

    // Init the cursors
    impl->m_HorizontalCursor = std::make_unique<VisualizationCursorItem>(&plot());
    impl->m_HorizontalCursor->setOrientation(Qt::Horizontal);
    impl->m_VerticalCursor = std::make_unique<VisualizationCursorItem>(&plot());
    impl->m_VerticalCursor->setOrientation(Qt::Vertical);

    this->setFocusPolicy(Qt::WheelFocus);
    this->setMouseTracking(true);
    impl->m_plot->setAttribute(Qt::WA_TransparentForMouseEvents);
    impl->m_plot->setContextMenuPolicy(Qt::CustomContextMenu);
    impl->m_plot->setParent(this);

    connect(&sqpApp->variableController(), &VariableController2::variableDeleted, this,
        &VisualizationGraphWidget::variableDeleted);
}


VisualizationGraphWidget::~VisualizationGraphWidget()
{
    delete ui;
}

VisualizationZoneWidget* VisualizationGraphWidget::parentZoneWidget() const noexcept
{
    auto parent = parentWidget();
    while (parent != nullptr && !qobject_cast<VisualizationZoneWidget*>(parent))
    {
        parent = parent->parentWidget();
    }

    return qobject_cast<VisualizationZoneWidget*>(parent);
}

VisualizationWidget* VisualizationGraphWidget::parentVisualizationWidget() const
{
    auto parent = parentWidget();
    while (parent != nullptr && !qobject_cast<VisualizationWidget*>(parent))
    {
        parent = parent->parentWidget();
    }

    return qobject_cast<VisualizationWidget*>(parent);
}

void VisualizationGraphWidget::setFlags(GraphFlags flags)
{
    impl->m_Flags = std::move(flags);
}

void VisualizationGraphWidget::addVariable(std::shared_ptr<Variable2> variable, DateTimeRange range)
{
    // Uses delegate to create the qcpplot components according to the variable
    auto createdPlottables = VisualizationGraphHelper::create(variable, *impl->m_plot);

    // Sets graph properties
    impl->m_RenderingDelegate->setGraphProperties(*variable, createdPlottables);

    impl->m_VariableToPlotMultiMap.insert({ variable, std::move(createdPlottables) });

    setGraphRange(range);
    // If the variable already has its data loaded, load its units and its range in the graph
    if (variable->data() != nullptr)
    {
        impl->m_RenderingDelegate->setAxesUnits(*variable);
    }
    else
    {
        auto context = new QObject { this };
        connect(
            variable.get(), &Variable2::updated, context, [this, variable, context, range](QUuid) {
                this->impl->m_RenderingDelegate->setAxesUnits(*variable);
                this->impl->m_plot->replot(QCustomPlot::rpQueuedReplot);
                delete context;
            });
    }
    //@TODO this is bad! when variable is moved to another graph it still fires
    // even if this has been deleted
    connect(variable.get(), &Variable2::updated, this, &VisualizationGraphWidget::variableUpdated);
    this->onUpdateVarDisplaying(variable, range); // My bullshit
    emit variableAdded(variable);
}

void VisualizationGraphWidget::removeVariable(std::shared_ptr<Variable2> variable) noexcept
{
    // Each component associated to the variable :
    // - is removed from qcpplot (which deletes it)
    // - is no longer referenced in the map
    auto variableIt = impl->m_VariableToPlotMultiMap.find(variable);
    if (variableIt != impl->m_VariableToPlotMultiMap.cend())
    {
        emit variableAboutToBeRemoved(variable);

        auto& plottablesMap = variableIt->second;

        for (auto plottableIt = plottablesMap.cbegin(), plottableEnd = plottablesMap.cend();
             plottableIt != plottableEnd;)
        {
            impl->m_plot->removePlottable(plottableIt->second);
            plottableIt = plottablesMap.erase(plottableIt);
        }

        impl->m_VariableToPlotMultiMap.erase(variableIt);
    }

    // Updates graph
    impl->m_plot->replot(QCustomPlot::rpQueuedReplot);
}

std::vector<std::shared_ptr<Variable2>> VisualizationGraphWidget::variables() const
{
    auto variables = std::vector<std::shared_ptr<Variable2>> {};
    for (auto it = std::cbegin(impl->m_VariableToPlotMultiMap);
         it != std::cend(impl->m_VariableToPlotMultiMap); ++it)
    {
        variables.push_back(it->first);
    }

    return variables;
}

void VisualizationGraphWidget::setYRange(std::shared_ptr<Variable2> variable)
{
    if (!variable)
    {
        qCCritical(LOG_VisualizationGraphWidget()) << "Can't set y-axis range: variable is null";
        return;
    }

    VisualizationGraphHelper::setYAxisRange(variable, *impl->m_plot);
}

DateTimeRange VisualizationGraphWidget::graphRange() const noexcept
{
    auto graphRange = impl->m_plot->xAxis->range();
    return DateTimeRange { graphRange.lower, graphRange.upper };
}

void VisualizationGraphWidget::setGraphRange(
    const DateTimeRange& range, bool updateVar, bool forward)
{
    impl->setRange(range, updateVar);
    if (forward)
    {
        emit this->setrange_sig(this->graphRange(), true, false);
    }
}

void VisualizationGraphWidget::setAutoRangeOnVariableInitialization(bool value)
{
    impl->m_VariableAutoRangeOnInit = value;
}

QVector<DateTimeRange> VisualizationGraphWidget::selectionZoneRanges() const
{
    QVector<DateTimeRange> ranges;
    for (auto zone : impl->m_SelectionZones)
    {
        ranges << zone->range();
    }

    return ranges;
}

void VisualizationGraphWidget::addSelectionZones(const QVector<DateTimeRange>& ranges)
{
    for (const auto& range : ranges)
    {
        // note: ownership is transfered to QCustomPlot
        auto zone = new VisualizationSelectionZoneItem(&plot());
        zone->setRange(range.m_TStart, range.m_TEnd);
        impl->addSelectionZone(zone);
    }

    plot().replot(QCustomPlot::rpQueuedReplot);
}

VisualizationSelectionZoneItem* VisualizationGraphWidget::addSelectionZone(
    const QString& name, const DateTimeRange& range)
{
    // note: ownership is transfered to QCustomPlot
    auto zone = new VisualizationSelectionZoneItem(&plot());
    zone->setName(name);
    zone->setRange(range.m_TStart, range.m_TEnd);
    impl->addSelectionZone(zone);

    plot().replot(QCustomPlot::rpQueuedReplot);

    return zone;
}

void VisualizationGraphWidget::removeSelectionZone(VisualizationSelectionZoneItem* selectionZone)
{
    parentVisualizationWidget()->selectionZoneManager().setSelected(selectionZone, false);

    if (impl->m_HoveredZone == selectionZone)
    {
        impl->m_HoveredZone = nullptr;
        setCursor(Qt::ArrowCursor);
    }

    impl->m_SelectionZones.removeAll(selectionZone);
    plot().removeItem(selectionZone);
    plot().replot(QCustomPlot::rpQueuedReplot);
}

void VisualizationGraphWidget::undoZoom()
{
    auto zoom = impl->m_ZoomStack.pop();
    auto axisX = plot().axisRect()->axis(QCPAxis::atBottom);
    auto axisY = plot().axisRect()->axis(QCPAxis::atLeft);

    axisX->setRange(zoom.first);
    axisY->setRange(zoom.second);

    plot().replot(QCustomPlot::rpQueuedReplot);
}

void VisualizationGraphWidget::zoom(
    double factor, int center, Qt::Orientation orientation, bool forward)
{
    impl->zoom(factor, center, orientation);
    if (forward && orientation == Qt::Horizontal)
        emit this->setrange_sig(this->graphRange(), true, false);
}

void VisualizationGraphWidget::move(double factor, Qt::Orientation orientation, bool forward)
{
    impl->move(factor, orientation);
    if (forward)
        emit this->setrange_sig(this->graphRange(), true, false);
}

void VisualizationGraphWidget::move(double dx, double dy, bool forward)
{
    impl->move(dx, dy);
    if (forward)
        emit this->setrange_sig(this->graphRange(), true, false);
}

void VisualizationGraphWidget::transform(
    const DateTimeRangeTransformation& tranformation, bool forward)
{
    impl->transform(tranformation);
    if (forward)
        emit this->setrange_sig(this->graphRange(), true, false);
}

void VisualizationGraphWidget::accept(IVisualizationWidgetVisitor* visitor)
{
    if (visitor)
    {
        visitor->visit(this);
    }
    else
    {
        qCCritical(LOG_VisualizationGraphWidget())
            << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationGraphWidget::canDrop(Variable2& variable) const
{
    auto isSpectrogram
        = [](auto& variable) { return variable.type() == DataSeriesType::SPECTROGRAM; };

    // - A spectrogram series can't be dropped on graph with existing plottables
    // - No data series can be dropped on graph with existing spectrogram series
    return isSpectrogram(variable)
        ? impl->m_VariableToPlotMultiMap.empty()
        : std::none_of(impl->m_VariableToPlotMultiMap.cbegin(),
              impl->m_VariableToPlotMultiMap.cend(),
              [isSpectrogram](const auto& entry) { return isSpectrogram(*entry.first); });
}

bool VisualizationGraphWidget::contains(Variable2& variable) const
{
    // Finds the variable among the keys of the map
    auto variablePtr = &variable;
    auto findVariable
        = [variablePtr](const auto& entry) { return variablePtr == entry.first.get(); };

    auto end = impl->m_VariableToPlotMultiMap.cend();
    auto it = std::find_if(impl->m_VariableToPlotMultiMap.cbegin(), end, findVariable);
    return it != end;
}

QString VisualizationGraphWidget::name() const
{
    return impl->m_Name;
}

QMimeData* VisualizationGraphWidget::mimeData(const QPoint& position) const
{
    auto mimeData = new QMimeData;

    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(position);
    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones
        && selectionZoneItemUnderCursor)
    {
        mimeData->setData(MIME_TYPE_TIME_RANGE,
            TimeController::mimeDataForTimeRange(selectionZoneItemUnderCursor->range()));
        mimeData->setData(MIME_TYPE_SELECTION_ZONE,
            TimeController::mimeDataForTimeRange(selectionZoneItemUnderCursor->range()));
    }
    else
    {
        mimeData->setData(MIME_TYPE_GRAPH, QByteArray {});

        auto timeRangeData = TimeController::mimeDataForTimeRange(graphRange());
        mimeData->setData(MIME_TYPE_TIME_RANGE, timeRangeData);
    }

    return mimeData;
}

QPixmap VisualizationGraphWidget::customDragPixmap(const QPoint& dragPosition)
{
    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(dragPosition);
    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones
        && selectionZoneItemUnderCursor)
    {

        auto zoneTopLeft = selectionZoneItemUnderCursor->topLeft->pixelPosition();
        auto zoneBottomRight = selectionZoneItemUnderCursor->bottomRight->pixelPosition();

        auto zoneSize = QSizeF { qAbs(zoneBottomRight.x() - zoneTopLeft.x()),
            qAbs(zoneBottomRight.y() - zoneTopLeft.y()) }
                            .toSize();

        auto pixmap = QPixmap(zoneSize);
        render(&pixmap, QPoint(), QRegion { QRect { zoneTopLeft.toPoint(), zoneSize } });

        return pixmap;
    }

    return QPixmap();
}

bool VisualizationGraphWidget::isDragAllowed() const
{
    return true;
}

void VisualizationGraphWidget::highlightForMerge(bool highlighted)
{
    if (highlighted)
    {
        plot().setBackground(QBrush(QColor("#BBD5EE")));
    }
    else
    {
        plot().setBackground(QBrush(Qt::white));
    }

    plot().update();
}

void VisualizationGraphWidget::addVerticalCursor(double time)
{
    impl->m_VerticalCursor->setPosition(time);
    impl->m_VerticalCursor->setVisible(true);

    auto text
        = DateUtils::dateTime(time).toString(CURSOR_LABELS_DATETIME_FORMAT).replace(' ', '\n');
    impl->m_VerticalCursor->setLabelText(text);
}

void VisualizationGraphWidget::addVerticalCursorAtViewportPosition(double position)
{
    impl->m_VerticalCursor->setAbsolutePosition(position);
    impl->m_VerticalCursor->setVisible(true);

    auto axis = plot().axisRect()->axis(QCPAxis::atBottom);
    auto text
        = DateUtils::dateTime(axis->pixelToCoord(position)).toString(CURSOR_LABELS_DATETIME_FORMAT);
    impl->m_VerticalCursor->setLabelText(text);
}

void VisualizationGraphWidget::removeVerticalCursor()
{
    impl->m_VerticalCursor->setVisible(false);
    plot().replot(QCustomPlot::rpQueuedReplot);
}

void VisualizationGraphWidget::addHorizontalCursor(double value)
{
    impl->m_HorizontalCursor->setPosition(value);
    impl->m_HorizontalCursor->setVisible(true);
    impl->m_HorizontalCursor->setLabelText(QString::number(value));
}

void VisualizationGraphWidget::addHorizontalCursorAtViewportPosition(double position)
{
    impl->m_HorizontalCursor->setAbsolutePosition(position);
    impl->m_HorizontalCursor->setVisible(true);

    auto axis = plot().axisRect()->axis(QCPAxis::atLeft);
    impl->m_HorizontalCursor->setLabelText(QString::number(axis->pixelToCoord(position)));
}

void VisualizationGraphWidget::removeHorizontalCursor()
{
    impl->m_HorizontalCursor->setVisible(false);
    plot().replot(QCustomPlot::rpQueuedReplot);
}

void VisualizationGraphWidget::closeEvent(QCloseEvent* event)
{
    Q_UNUSED(event);

    for (auto i : impl->m_SelectionZones)
    {
        parentVisualizationWidget()->selectionZoneManager().setSelected(i, false);
    }

    // Prevents that all variables will be removed from graph when it will be closed
    for (auto& variableEntry : impl->m_VariableToPlotMultiMap)
    {
        emit variableAboutToBeRemoved(variableEntry.first);
    }
}

void VisualizationGraphWidget::enterEvent(QEvent* event)
{
    Q_UNUSED(event);
    impl->m_RenderingDelegate->showGraphOverlay(true);
}

void VisualizationGraphWidget::leaveEvent(QEvent* event)
{
    Q_UNUSED(event);
    impl->m_RenderingDelegate->showGraphOverlay(false);

    if (auto parentZone = parentZoneWidget())
    {
        parentZone->notifyMouseLeaveGraph(this);
    }
    else
    {
        qCWarning(LOG_VisualizationGraphWidget()) << "leaveEvent: No parent zone widget";
    }

    if (impl->m_HoveredZone)
    {
        impl->m_HoveredZone->setHovered(false);
        impl->m_HoveredZone = nullptr;
    }
}

void VisualizationGraphWidget::wheelEvent(QWheelEvent* event)
{
    double factor;
    double wheelSteps = event->delta() / 120.0; // a single step delta is +/-120 usually
    if (event->modifiers() == Qt::ControlModifier)
    {
        if (event->orientation() == Qt::Vertical) // mRangeZoom.testFlag(Qt::Vertical))
        {
            setCursor(Qt::SizeVerCursor);
            factor = pow(impl->m_plot->axisRect()->rangeZoomFactor(Qt::Vertical), wheelSteps);
            zoom(factor, event->pos().y(), Qt::Vertical);
        }
    }
    else if (event->modifiers() == Qt::ShiftModifier)
    {
        if (event->orientation() == Qt::Vertical) // mRangeZoom.testFlag(Qt::Vertical))
        {
            setCursor(Qt::SizeHorCursor);
            factor = pow(impl->m_plot->axisRect()->rangeZoomFactor(Qt::Horizontal), wheelSteps);
            zoom(factor, event->pos().x(), Qt::Horizontal);
        }
    }
    else
    {
        move(wheelSteps, Qt::Horizontal);
    }
    event->accept();
}


void VisualizationGraphWidget::mouseMoveEvent(QMouseEvent* event)
{
    if (impl->isDrawingZoomRect())
    {
        impl->updateZoomRect(event->pos());
    }
    else if (impl->isDrawingZoneRect())
    {
        impl->updateZoneRect(event->pos());
    }
    else if (event->buttons() == Qt::LeftButton)
    {
        if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::None)
        {
            auto [dx, dy] = impl->moveGraph(event->pos());
            emit this->setrange_sig(this->graphRange(), true, false);
        }
        else if (sqpApp->plotsInteractionMode()
            == SqpApplication::PlotsInteractionMode::SelectionZones)
        {
            auto posInPlot = this->impl->m_plot->mapFromParent(event->pos());
            if (auto item = impl->m_plot->itemAt(posInPlot))
            {
                if (qobject_cast<VisualizationSelectionZoneItem*>(item))
                {
                    QMouseEvent e { QEvent::MouseMove, posInPlot, event->button(), event->buttons(),
                        event->modifiers() };
                    sqpApp->sendEvent(this->impl->m_plot, &e);
                    this->impl->m_plot->replot(QCustomPlot::rpImmediateRefresh);
                }
            }
        }
    }
    else
    {
        impl->m_RenderingDelegate->updateTooltip(event);
    }
    // event->accept();
    QWidget::mouseMoveEvent(event);
}

void VisualizationGraphWidget::mouseReleaseEvent(QMouseEvent* event)
{
    if (impl->isDrawingZoomRect())
    {
        auto oldRange = this->graphRange();
        impl->applyZoomRect();
        auto newRange = this->graphRange();
        if (auto tf = DateTimeRangeHelper::computeTransformation(oldRange, newRange))
            emit this->transform_sig(tf.value(), false);
    }
    else if (impl->isDrawingZoneRect())
    {
        impl->endDrawingZone();
    }
    else
    {
        setCursor(Qt::ArrowCursor);
    }
    auto posInPlot = this->impl->m_plot->mapFromParent(event->pos());
    if (auto item = impl->m_plot->itemAt(posInPlot))
    {
        if (qobject_cast<VisualizationSelectionZoneItem*>(item))
        {
            QMouseEvent e { QEvent::MouseButtonRelease, posInPlot, event->button(),
                event->buttons(), event->modifiers() };
            sqpApp->sendEvent(this->impl->m_plot, &e);
        }
    }
    event->accept();
}

void VisualizationGraphWidget::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::RightButton)
    {
        onGraphMenuRequested(event->pos());
    }
    else
    {
        auto selectedZone = impl->selectionZoneAt(event->pos());
        switch (sqpApp->plotsInteractionMode())
        {
            case SqpApplication::PlotsInteractionMode::DragAndDrop:
                break;
            case SqpApplication::PlotsInteractionMode::SelectionZones:
                impl->setSelectionZonesEditionEnabled(true);
                if ((event->modifiers() == Qt::ControlModifier) && (selectedZone != nullptr))
                {
                    auto alreadySelectedZones
                        = parentVisualizationWidget()->selectionZoneManager().selectedItems();
                    selectedZone->setAssociatedEditedZones(alreadySelectedZones);
                    if (SciQLop::containers::contains(alreadySelectedZones, selectedZone))
                    {
                        alreadySelectedZones.removeOne(selectedZone);
                    }
                    else
                    {
                        alreadySelectedZones.append(selectedZone);
                    }
                    parentVisualizationWidget()->selectionZoneManager().select(
                        alreadySelectedZones);
                }
                else
                {
                    if (!selectedZone)
                    {
                        parentVisualizationWidget()->selectionZoneManager().clearSelection();
                        impl->startDrawingZone(event->pos());
                    }
                    else
                    {
                        parentVisualizationWidget()->selectionZoneManager().select(
                            { selectedZone });
                    }
                }
                {
                    auto posInPlot = this->impl->m_plot->mapFromParent(event->pos());
                    if (auto item = impl->m_plot->itemAt(posInPlot))
                    {
                        if (qobject_cast<VisualizationSelectionZoneItem*>(item))
                        {
                            QMouseEvent e { QEvent::MouseButtonPress, posInPlot, event->button(),
                                event->buttons(), event->modifiers() };
                            sqpApp->sendEvent(this->impl->m_plot, &e);
                        }
                    }
                }
                break;
            case SqpApplication::PlotsInteractionMode::ZoomBox:
                impl->startDrawingRect(event->pos());
                break;
            default:
                if (auto item = impl->m_plot->itemAt(event->pos()))
                {
                    emit impl->m_plot->itemClick(item, event);
                    if (qobject_cast<VisualizationSelectionZoneItem*>(item))
                    {
                        setCursor(Qt::ClosedHandCursor);
                        impl->enterPlotDrag(event->pos());
                    }
                }
                else
                {
                    setCursor(Qt::ClosedHandCursor);
                    impl->enterPlotDrag(event->pos());
                }
        }
    }
    // event->accept();
    QWidget::mousePressEvent(event);
}

void VisualizationGraphWidget::mouseDoubleClickEvent(QMouseEvent* event)
{
    impl->m_RenderingDelegate->onMouseDoubleClick(event);
}

void VisualizationGraphWidget::keyReleaseEvent(QKeyEvent* event)
{
    switch (event->key())
    {
        case Qt::Key_Control:
            event->accept();
            break;
        case Qt::Key_Shift:
            event->accept();
            break;
        default:
            QWidget::keyReleaseEvent(event);
            break;
    }
    setCursor(Qt::ArrowCursor);
    // event->accept();
}

void VisualizationGraphWidget::keyPressEvent(QKeyEvent* event)
{
    switch (event->key())
    {
        case Qt::Key_Control:
            setCursor(Qt::CrossCursor);
            break;
        case Qt::Key_Shift:
            break;
        case Qt::Key_M:
            impl->rescaleY();
            impl->m_plot->replot(QCustomPlot::rpQueuedReplot);
            break;
        case Qt::Key_Left:
            if (event->modifiers() != Qt::ControlModifier)
            {
                move(-0.1, Qt::Horizontal);
            }
            else
            {
                zoom(2, this->width() / 2, Qt::Horizontal);
            }
            break;
        case Qt::Key_Right:
            if (event->modifiers() != Qt::ControlModifier)
            {
                move(0.1, Qt::Horizontal);
            }
            else
            {
                zoom(0.5, this->width() / 2, Qt::Horizontal);
            }
            break;
        case Qt::Key_Up:
            if (event->modifiers() != Qt::ControlModifier)
            {
                move(0.1, Qt::Vertical);
            }
            else
            {
                zoom(0.5, this->height() / 2, Qt::Vertical);
            }
            break;
        case Qt::Key_Down:
            if (event->modifiers() != Qt::ControlModifier)
            {
                move(-0.1, Qt::Vertical);
            }
            else
            {
                zoom(2, this->height() / 2, Qt::Vertical);
            }
            break;
        default:
            QWidget::keyPressEvent(event);
            break;
    }
}

QCustomPlot& VisualizationGraphWidget::plot() const noexcept
{
    return *impl->m_plot;
}

void VisualizationGraphWidget::onGraphMenuRequested(const QPoint& pos) noexcept
{
    QMenu graphMenu {};

    // Iterates on variables (unique keys)
    for (auto it = impl->m_VariableToPlotMultiMap.cbegin(),
              end = impl->m_VariableToPlotMultiMap.cend();
         it != end; it = impl->m_VariableToPlotMultiMap.upper_bound(it->first))
    {
        // 'Remove variable' action
        graphMenu.addAction(tr("Remove variable %1").arg(it->first->name()),
            [this, var = it->first]() { removeVariable(var); });
    }

    if (!impl->m_ZoomStack.isEmpty())
    {
        if (!graphMenu.isEmpty())
        {
            graphMenu.addSeparator();
        }

        graphMenu.addAction(tr("Undo Zoom"), [this]() { undoZoom(); });
    }

    // Selection Zone Actions
    auto selectionZoneItem = impl->selectionZoneAt(pos);
    if (selectionZoneItem)
    {
        auto selectedItems = parentVisualizationWidget()->selectionZoneManager().selectedItems();
        selectedItems.removeAll(selectionZoneItem);
        selectedItems.prepend(selectionZoneItem); // Put the current selection zone first

        auto zoneActions = sqpApp->actionsGuiController().selectionZoneActions();
        if (!zoneActions.isEmpty() && !graphMenu.isEmpty())
        {
            graphMenu.addSeparator();
        }

        QHash<QString, QMenu*> subMenus;
        QHash<QString, bool> subMenusEnabled;
        QHash<QString, FilteringAction*> filteredMenu;

        for (auto zoneAction : zoneActions)
        {

            auto isEnabled = zoneAction->isEnabled(selectedItems);

            auto menu = &graphMenu;
            QString menuPath;
            for (auto subMenuName : zoneAction->subMenuList())
            {
                menuPath += '/';
                menuPath += subMenuName;

                if (!subMenus.contains(menuPath))
                {
                    menu = menu->addMenu(subMenuName);
                    subMenus[menuPath] = menu;
                    subMenusEnabled[menuPath] = isEnabled;
                }
                else
                {
                    menu = subMenus.value(menuPath);
                    if (isEnabled)
                    {
                        // The sub menu is enabled if at least one of its actions is enabled
                        subMenusEnabled[menuPath] = true;
                    }
                }
            }

            FilteringAction* filterAction = nullptr;
            if (sqpApp->actionsGuiController().isMenuFiltered(zoneAction->subMenuList()))
            {
                filterAction = filteredMenu.value(menuPath);
                if (!filterAction)
                {
                    filterAction = new FilteringAction { this };
                    filteredMenu[menuPath] = filterAction;
                    menu->addAction(filterAction);
                }
            }

            auto action = menu->addAction(zoneAction->name());
            action->setEnabled(isEnabled);
            action->setShortcut(zoneAction->displayedShortcut());
            QObject::connect(action, &QAction::triggered,
                [zoneAction, selectedItems]() { zoneAction->execute(selectedItems); });

            if (filterAction && zoneAction->isFilteringAllowed())
            {
                filterAction->addActionToFilter(action);
            }
        }

        for (auto it = subMenus.cbegin(); it != subMenus.cend(); ++it)
        {
            it.value()->setEnabled(subMenusEnabled[it.key()]);
        }
    }

    if (!graphMenu.isEmpty())
    {
        graphMenu.exec(QCursor::pos());
    }
}

void VisualizationGraphWidget::onMouseDoubleClick(QMouseEvent* event) noexcept
{
    impl->m_RenderingDelegate->onMouseDoubleClick(event);
}

void VisualizationGraphWidget::onMouseMove(QMouseEvent* event) noexcept
{
    // Handles plot rendering when mouse is moving
    impl->m_RenderingDelegate->updateTooltip(event);

    auto axisPos = impl->posToAxisPos(event->pos());

    // Zoom box and zone drawing
    if (impl->m_DrawingZoomRect)
    {
        impl->m_DrawingZoomRect->bottomRight->setCoords(axisPos);
    }
    else if (impl->m_DrawingZone)
    {
        impl->m_DrawingZone->setEnd(axisPos.x());
    }

    // Cursor
    if (auto parentZone = parentZoneWidget())
    {
        if (impl->pointIsInAxisRect(axisPos, plot()))
        {
            parentZone->notifyMouseMoveInGraph(event->pos(), axisPos, this);
        }
        else
        {
            parentZone->notifyMouseLeaveGraph(this);
        }
    }

    // Search for the selection zone under the mouse
    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos());
    if (selectionZoneItemUnderCursor && !impl->m_DrawingZone
        && sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones)
    {

        // Sets the appropriate cursor shape
        auto cursorShape = selectionZoneItemUnderCursor->curshorShapeForPosition(event->pos());
        setCursor(cursorShape);

        // Manages the hovered zone
        if (selectionZoneItemUnderCursor != impl->m_HoveredZone)
        {
            if (impl->m_HoveredZone)
            {
                impl->m_HoveredZone->setHovered(false);
            }
            selectionZoneItemUnderCursor->setHovered(true);
            impl->m_HoveredZone = selectionZoneItemUnderCursor;
            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }
    else
    {
        // There is no zone under the mouse or the interaction mode is not "selection zones"
        if (impl->m_HoveredZone)
        {
            impl->m_HoveredZone->setHovered(false);
            impl->m_HoveredZone = nullptr;
        }

        setCursor(Qt::ArrowCursor);
    }

    impl->m_HasMovedMouse = true;
    VisualizationDragWidget::mouseMoveEvent(event);
}

void VisualizationGraphWidget::onMouseWheel(QWheelEvent* event) noexcept
{
    // Processes event only if the wheel occurs on axis rect
    if (!dynamic_cast<QCPAxisRect*>(impl->m_plot->layoutElementAt(event->posF())))
    {
        return;
    }

    auto value = event->angleDelta().x() + event->angleDelta().y();
    if (value != 0)
    {

        auto direction = value > 0 ? 1.0 : -1.0;
        auto isZoomX = event->modifiers().testFlag(HORIZONTAL_ZOOM_MODIFIER);
        auto isZoomY = event->modifiers().testFlag(VERTICAL_ZOOM_MODIFIER);
        impl->m_IsCalibration = event->modifiers().testFlag(VERTICAL_PAN_MODIFIER);

        auto zoomOrientations = QFlags<Qt::Orientation> {};
        zoomOrientations.setFlag(Qt::Horizontal, isZoomX);
        zoomOrientations.setFlag(Qt::Vertical, isZoomY);

        impl->m_plot->axisRect()->setRangeZoom(zoomOrientations);

        if (!isZoomX && !isZoomY)
        {
            auto axis = plot().axisRect()->axis(QCPAxis::atBottom);
            auto diff = direction * (axis->range().size() * (PAN_SPEED / 100.0));

            axis->setRange(axis->range() + diff);

            if (plot().noAntialiasingOnDrag())
            {
                plot().setNotAntialiasedElements(QCP::aeAll);
            }

            // plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }
}

void VisualizationGraphWidget::onMousePress(QMouseEvent* event) noexcept
{
    auto isDragDropClick = event->modifiers().testFlag(DRAG_DROP_MODIFIER);
    auto isSelectionZoneMode
        = sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones;
    auto isLeftClick = event->buttons().testFlag(Qt::LeftButton);

    if (!isDragDropClick && isLeftClick)
    {
        if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::ZoomBox)
        {
            // Starts a zoom box
            impl->startDrawingRect(event->pos());
        }
        else if (isSelectionZoneMode && impl->m_DrawingZone == nullptr)
        {
            // Starts a new selection zone
            auto zoneAtPos = impl->selectionZoneAt(event->pos());
            if (!zoneAtPos)
            {
                impl->startDrawingZone(event->pos());
            }
        }
    }


    // Allows zone edition only in selection zone mode without drag&drop
    impl->setSelectionZonesEditionEnabled(isSelectionZoneMode && !isDragDropClick);

    // Selection / Deselection
    if (isSelectionZoneMode)
    {
        auto isMultiSelectionClick = event->modifiers().testFlag(MULTI_ZONE_SELECTION_MODIFIER);
        auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos());


        if (selectionZoneItemUnderCursor && !selectionZoneItemUnderCursor->selected()
            && !isMultiSelectionClick)
        {
            parentVisualizationWidget()->selectionZoneManager().select(
                { selectionZoneItemUnderCursor });
        }
        else if (!selectionZoneItemUnderCursor && !isMultiSelectionClick && isLeftClick)
        {
            parentVisualizationWidget()->selectionZoneManager().clearSelection();
        }
        else
        {
            // No selection change
        }

        if (selectionZoneItemUnderCursor && isLeftClick)
        {
            selectionZoneItemUnderCursor->setAssociatedEditedZones(
                parentVisualizationWidget()->selectionZoneManager().selectedItems());
        }
    }


    impl->m_HasMovedMouse = false;
    VisualizationDragWidget::mousePressEvent(event);
}

void VisualizationGraphWidget::onMouseRelease(QMouseEvent* event) noexcept
{
    if (impl->m_DrawingZoomRect)
    {

        auto axisX = plot().axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot().axisRect()->axis(QCPAxis::atLeft);

        auto newAxisXRange = QCPRange { impl->m_DrawingZoomRect->topLeft->coords().x(),
            impl->m_DrawingZoomRect->bottomRight->coords().x() };

        auto newAxisYRange = QCPRange { impl->m_DrawingZoomRect->topLeft->coords().y(),
            impl->m_DrawingZoomRect->bottomRight->coords().y() };

        impl->removeDrawingRect();

        if (newAxisXRange.size() > axisX->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)
            && newAxisYRange.size() > axisY->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0))
        {
            impl->m_ZoomStack.push(qMakePair(axisX->range(), axisY->range()));
            axisX->setRange(newAxisXRange);
            axisY->setRange(newAxisYRange);

            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }

    impl->endDrawingZone();

    // Selection / Deselection
    auto isSelectionZoneMode
        = sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones;
    if (isSelectionZoneMode)
    {
        auto isMultiSelectionClick = event->modifiers().testFlag(MULTI_ZONE_SELECTION_MODIFIER);
        auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos());
        if (selectionZoneItemUnderCursor && event->button() == Qt::LeftButton
            && !impl->m_HasMovedMouse)
        {

            auto zonesUnderCursor = impl->selectionZonesAt(event->pos(), plot());
            if (zonesUnderCursor.count() > 1)
            {
                // There are multiple zones under the mouse.
                // Performs the selection with a selection dialog.
                VisualizationMultiZoneSelectionDialog dialog { this };
                dialog.setZones(zonesUnderCursor);
                dialog.move(mapToGlobal(event->pos() - QPoint(dialog.width() / 2, 20)));
                dialog.activateWindow();
                dialog.raise();
                if (dialog.exec() == QDialog::Accepted)
                {
                    auto selection = dialog.selectedZones();

                    if (!isMultiSelectionClick)
                    {
                        parentVisualizationWidget()->selectionZoneManager().clearSelection();
                    }

                    for (auto it = selection.cbegin(); it != selection.cend(); ++it)
                    {
                        auto zone = it.key();
                        auto isSelected = it.value();
                        parentVisualizationWidget()->selectionZoneManager().setSelected(
                            zone, isSelected);

                        if (isSelected)
                        {
                            // Puts the zone on top of the stack so it can be moved or resized
                            impl->moveSelectionZoneOnTop(zone, plot());
                        }
                    }
                }
            }
            else
            {
                if (!isMultiSelectionClick)
                {
                    parentVisualizationWidget()->selectionZoneManager().select(
                        { selectionZoneItemUnderCursor });
                    impl->moveSelectionZoneOnTop(selectionZoneItemUnderCursor, plot());
                }
                else
                {
                    parentVisualizationWidget()->selectionZoneManager().setSelected(
                        selectionZoneItemUnderCursor,
                        !selectionZoneItemUnderCursor->selected()
                            || event->button() == Qt::RightButton);
                }
            }
        }
        else
        {
            // No selection change
        }
    }
}

void VisualizationGraphWidget::onDataCacheVariableUpdated()
{
    auto graphRange = impl->m_plot->xAxis->range();
    auto dateTime = DateTimeRange { graphRange.lower, graphRange.upper };

    for (auto& variableEntry : impl->m_VariableToPlotMultiMap)
    {
        auto variable = variableEntry.first;
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated S" << variable->range();
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated E" << dateTime;
        if (dateTime.contains(variable->range()) || dateTime.intersect(variable->range()))
        {
            impl->updateData(variableEntry.second, variable, variable->range());
        }
    }
}

void VisualizationGraphWidget::onUpdateVarDisplaying(
    std::shared_ptr<Variable2> variable, const DateTimeRange& range)
{
    auto it = impl->m_VariableToPlotMultiMap.find(variable);
    if (it != impl->m_VariableToPlotMultiMap.end())
    {
        impl->updateData(it->second, variable, range);
    }
}

void VisualizationGraphWidget::variableUpdated(QUuid id)
{
    for (auto& [var, plotables] : impl->m_VariableToPlotMultiMap)
    {
        if (var->ID() == id)
        {
            impl->updateData(plotables, var, this->graphRange());
        }
    }
}

void VisualizationGraphWidget::variableDeleted(const std::shared_ptr<Variable2>& variable)
{
    this->removeVariable(variable);
}
