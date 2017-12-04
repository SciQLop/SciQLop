#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationCursorItem.h"
#include "Visualization/VisualizationDefs.h"
#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/VisualizationSelectionZoneItem.h"
#include "Visualization/VisualizationSelectionZoneManager.h"
#include "Visualization/VisualizationWidget.h"
#include "Visualization/VisualizationZoneWidget.h"
#include "ui_VisualizationGraphWidget.h"

#include <Actions/ActionsGuiController.h>
#include <Common/MimeTypesDef.h>
#include <Data/ArrayData.h>
#include <Data/IDataSeries.h>
#include <Data/SpectrogramSeries.h>
#include <DragAndDrop/DragDropGuiController.h>
#include <Settings/SqpSettingsDefs.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphWidget, "VisualizationGraphWidget")

namespace {

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

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate {

    explicit VisualizationGraphWidgetPrivate(const QString &name)
            : m_Name{name},
              m_DoAcquisition{true},
              m_IsCalibration{false},
              m_RenderingDelegate{nullptr}
    {
    }

    void updateData(PlottablesMap &plottables, std::shared_ptr<IDataSeries> dataSeries,
                    const SqpRange &range)
    {
        VisualizationGraphHelper::updateData(plottables, dataSeries, range);

        // Prevents that data has changed to update rendering
        m_RenderingDelegate->onPlotUpdated();
    }

    QString m_Name;
    // 1 variable -> n qcpplot
    std::map<std::shared_ptr<Variable>, PlottablesMap> m_VariableToPlotMultiMap;
    bool m_DoAcquisition;
    bool m_IsCalibration;
    /// Delegate used to attach rendering features to the plot
    std::unique_ptr<VisualizationGraphRenderingDelegate> m_RenderingDelegate;

    QCPItemRect *m_DrawingZoomRect = nullptr;
    QStack<QPair<QCPRange, QCPRange> > m_ZoomStack;

    std::unique_ptr<VisualizationCursorItem> m_HorizontalCursor = nullptr;
    std::unique_ptr<VisualizationCursorItem> m_VerticalCursor = nullptr;

    VisualizationSelectionZoneItem *m_DrawingZone = nullptr;
    VisualizationSelectionZoneItem *m_HoveredZone = nullptr;
    QVector<VisualizationSelectionZoneItem *> m_SelectionZones;

    bool m_HasMovedMouse = false; // Indicates if the mouse moved in a releaseMouse even

    void startDrawingRect(const QPoint &pos, QCustomPlot &plot)
    {
        removeDrawingRect(plot);

        auto axisPos = posToAxisPos(pos, plot);

        m_DrawingZoomRect = new QCPItemRect{&plot};
        QPen p;
        p.setWidth(2);
        m_DrawingZoomRect->setPen(p);

        m_DrawingZoomRect->topLeft->setCoords(axisPos);
        m_DrawingZoomRect->bottomRight->setCoords(axisPos);
    }

    void removeDrawingRect(QCustomPlot &plot)
    {
        if (m_DrawingZoomRect) {
            plot.removeItem(m_DrawingZoomRect); // the item is deleted by QCustomPlot
            m_DrawingZoomRect = nullptr;
            plot.replot(QCustomPlot::rpQueuedReplot);
        }
    }

    void startDrawingZone(const QPoint &pos, VisualizationGraphWidget *graph)
    {
        endDrawingZone(graph);

        auto axisPos = posToAxisPos(pos, graph->plot());

        m_DrawingZone = new VisualizationSelectionZoneItem{&graph->plot()};
        m_DrawingZone->setRange(axisPos.x(), axisPos.x());
        m_DrawingZone->setEditionEnabled(false);
    }

    void endDrawingZone(VisualizationGraphWidget *graph)
    {
        if (m_DrawingZone) {
            auto drawingZoneRange = m_DrawingZone->range();
            if (qAbs(drawingZoneRange.m_TEnd - drawingZoneRange.m_TStart) > 0) {
                m_DrawingZone->setEditionEnabled(true);
                addSelectionZone(m_DrawingZone);
            }
            else {
                graph->plot().removeItem(m_DrawingZone); // the item is deleted by QCustomPlot
            }

            graph->plot().replot(QCustomPlot::rpQueuedReplot);
            m_DrawingZone = nullptr;
        }
    }

    void setSelectionZonesEditionEnabled(bool value)
    {
        for (auto s : m_SelectionZones) {
            s->setEditionEnabled(value);
        }
    }

    void addSelectionZone(VisualizationSelectionZoneItem *zone) { m_SelectionZones << zone; }

    VisualizationSelectionZoneItem *selectionZoneAt(const QPoint &pos,
                                                    const QCustomPlot &plot) const
    {
        VisualizationSelectionZoneItem *selectionZoneItemUnderCursor = nullptr;
        auto minDistanceToZone = -1;
        for (auto zone : m_SelectionZones) {
            auto distanceToZone = zone->selectTest(pos, false);
            if ((minDistanceToZone < 0 || distanceToZone <= minDistanceToZone)
                && distanceToZone >= 0 && distanceToZone < plot.selectionTolerance()) {
                selectionZoneItemUnderCursor = zone;
            }
        }

        return selectionZoneItemUnderCursor;
    }

    QPointF posToAxisPos(const QPoint &pos, QCustomPlot &plot) const
    {
        auto axisX = plot.axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot.axisRect()->axis(QCPAxis::atLeft);
        return QPointF{axisX->pixelToCoord(pos.x()), axisY->pixelToCoord(pos.y())};
    }

    bool pointIsInAxisRect(const QPointF &axisPoint, QCustomPlot &plot) const
    {
        auto axisX = plot.axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot.axisRect()->axis(QCPAxis::atLeft);
        return axisX->range().contains(axisPoint.x()) && axisY->range().contains(axisPoint.y());
    }
};

VisualizationGraphWidget::VisualizationGraphWidget(const QString &name, QWidget *parent)
        : VisualizationDragWidget{parent},
          ui{new Ui::VisualizationGraphWidget},
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>(name)}
{
    ui->setupUi(this);

    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);

    // Set qcpplot properties :
    // - zoom is enabled
    // - Mouse wheel on qcpplot is intercepted to determine the zoom orientation
    ui->widget->setInteractions(QCP::iRangeZoom);
    ui->widget->axisRect()->setRangeDrag(Qt::Horizontal | Qt::Vertical);

    // The delegate must be initialized after the ui as it uses the plot
    impl->m_RenderingDelegate = std::make_unique<VisualizationGraphRenderingDelegate>(*this);

    // Init the cursors
    impl->m_HorizontalCursor = std::make_unique<VisualizationCursorItem>(&plot());
    impl->m_HorizontalCursor->setOrientation(Qt::Horizontal);
    impl->m_VerticalCursor = std::make_unique<VisualizationCursorItem>(&plot());
    impl->m_VerticalCursor->setOrientation(Qt::Vertical);

    connect(ui->widget, &QCustomPlot::mousePress, this, &VisualizationGraphWidget::onMousePress);
    connect(ui->widget, &QCustomPlot::mouseRelease, this,
            &VisualizationGraphWidget::onMouseRelease);
    connect(ui->widget, &QCustomPlot::mouseMove, this, &VisualizationGraphWidget::onMouseMove);
    connect(ui->widget, &QCustomPlot::mouseWheel, this, &VisualizationGraphWidget::onMouseWheel);
    connect(ui->widget, &QCustomPlot::mouseDoubleClick, this,
            &VisualizationGraphWidget::onMouseDoubleClick);
    connect(
        ui->widget->xAxis,
        static_cast<void (QCPAxis::*)(const QCPRange &, const QCPRange &)>(&QCPAxis::rangeChanged),
        this, &VisualizationGraphWidget::onRangeChanged, Qt::DirectConnection);

    // Activates menu when right clicking on the graph
    ui->widget->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->widget, &QCustomPlot::customContextMenuRequested, this,
            &VisualizationGraphWidget::onGraphMenuRequested);

    connect(this, &VisualizationGraphWidget::requestDataLoading, &sqpApp->variableController(),
            &VariableController::onRequestDataLoading);

    connect(&sqpApp->variableController(), &VariableController::updateVarDisplaying, this,
            &VisualizationGraphWidget::onUpdateVarDisplaying);

#ifdef Q_OS_MAC
    plot().setPlottingHint(QCP::phFastPolylines, true);
#endif
}


VisualizationGraphWidget::~VisualizationGraphWidget()
{
    delete ui;
}

VisualizationZoneWidget *VisualizationGraphWidget::parentZoneWidget() const noexcept
{
    auto parent = parentWidget();
    while (parent != nullptr && !qobject_cast<VisualizationZoneWidget *>(parent)) {
        parent = parent->parentWidget();
    }

    return qobject_cast<VisualizationZoneWidget *>(parent);
}

VisualizationWidget *VisualizationGraphWidget::parentVisualizationWidget() const
{
    auto parent = parentWidget();
    while (parent != nullptr && !qobject_cast<VisualizationWidget *>(parent)) {
        parent = parent->parentWidget();
    }

    return qobject_cast<VisualizationWidget *>(parent);
}

void VisualizationGraphWidget::enableAcquisition(bool enable)
{
    impl->m_DoAcquisition = enable;
}

void VisualizationGraphWidget::addVariable(std::shared_ptr<Variable> variable, SqpRange range)
{
    // Uses delegate to create the qcpplot components according to the variable
    auto createdPlottables = VisualizationGraphHelper::create(variable, *ui->widget);

    if (auto dataSeries = variable->dataSeries()) {
        // Set axes properties according to the units of the data series
        impl->m_RenderingDelegate->setAxesProperties(dataSeries);

        // Sets rendering properties for the new plottables
        // Warning: this method must be called after setAxesProperties(), as it can access to some
        // axes properties that have to be initialized
        impl->m_RenderingDelegate->setPlottablesProperties(dataSeries, createdPlottables);
    }

    impl->m_VariableToPlotMultiMap.insert({variable, std::move(createdPlottables)});

    connect(variable.get(), SIGNAL(updated()), this, SLOT(onDataCacheVariableUpdated()));

    this->enableAcquisition(false);
    this->setGraphRange(range);
    this->enableAcquisition(true);

    emit requestDataLoading(QVector<std::shared_ptr<Variable> >() << variable, range, false);

    emit variableAdded(variable);
}

void VisualizationGraphWidget::removeVariable(std::shared_ptr<Variable> variable) noexcept
{
    // Each component associated to the variable :
    // - is removed from qcpplot (which deletes it)
    // - is no longer referenced in the map
    auto variableIt = impl->m_VariableToPlotMultiMap.find(variable);
    if (variableIt != impl->m_VariableToPlotMultiMap.cend()) {
        emit variableAboutToBeRemoved(variable);

        auto &plottablesMap = variableIt->second;

        for (auto plottableIt = plottablesMap.cbegin(), plottableEnd = plottablesMap.cend();
             plottableIt != plottableEnd;) {
            ui->widget->removePlottable(plottableIt->second);
            plottableIt = plottablesMap.erase(plottableIt);
        }

        impl->m_VariableToPlotMultiMap.erase(variableIt);
    }

    // Updates graph
    ui->widget->replot();
}

QList<std::shared_ptr<Variable> > VisualizationGraphWidget::variables() const
{
    auto variables = QList<std::shared_ptr<Variable> >{};
    for (auto it = std::cbegin(impl->m_VariableToPlotMultiMap);
         it != std::cend(impl->m_VariableToPlotMultiMap); ++it) {
        variables << it->first;
    }

    return variables;
}

void VisualizationGraphWidget::setYRange(std::shared_ptr<Variable> variable)
{
    if (!variable) {
        qCCritical(LOG_VisualizationGraphWidget()) << "Can't set y-axis range: variable is null";
        return;
    }

    VisualizationGraphHelper::setYAxisRange(variable, *ui->widget);
}

SqpRange VisualizationGraphWidget::graphRange() const noexcept
{
    auto graphRange = ui->widget->xAxis->range();
    return SqpRange{graphRange.lower, graphRange.upper};
}

void VisualizationGraphWidget::setGraphRange(const SqpRange &range)
{
    qCDebug(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::setGraphRange START");
    ui->widget->xAxis->setRange(range.m_TStart, range.m_TEnd);
    ui->widget->replot();
    qCDebug(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::setGraphRange END");
}

QVector<SqpRange> VisualizationGraphWidget::selectionZoneRanges() const
{
    QVector<SqpRange> ranges;
    for (auto zone : impl->m_SelectionZones) {
        ranges << zone->range();
    }

    return ranges;
}

void VisualizationGraphWidget::addSelectionZones(const QVector<SqpRange> &ranges)
{
    for (const auto &range : ranges) {
        // note: ownership is transfered to QCustomPlot
        auto zone = new VisualizationSelectionZoneItem(&plot());
        zone->setRange(range.m_TStart, range.m_TEnd);
        impl->addSelectionZone(zone);
    }

    plot().replot(QCustomPlot::rpQueuedReplot);
}

void VisualizationGraphWidget::removeSelectionZone(VisualizationSelectionZoneItem *selectionZone)
{
    parentVisualizationWidget()->selectionZoneManager().setSelected(selectionZone, false);

    if (impl->m_HoveredZone == selectionZone) {
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

void VisualizationGraphWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visit(this);
    }
    else {
        qCCritical(LOG_VisualizationGraphWidget())
            << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationGraphWidget::canDrop(const Variable &variable) const
{
    auto isSpectrogram = [](const auto &variable) {
        return std::dynamic_pointer_cast<SpectrogramSeries>(variable.dataSeries()) != nullptr;
    };

    // - A spectrogram series can't be dropped on graph with existing plottables
    // - No data series can be dropped on graph with existing spectrogram series
    return isSpectrogram(variable)
               ? impl->m_VariableToPlotMultiMap.empty()
               : std::none_of(
                     impl->m_VariableToPlotMultiMap.cbegin(), impl->m_VariableToPlotMultiMap.cend(),
                     [isSpectrogram](const auto &entry) { return isSpectrogram(*entry.first); });
}

bool VisualizationGraphWidget::contains(const Variable &variable) const
{
    // Finds the variable among the keys of the map
    auto variablePtr = &variable;
    auto findVariable
        = [variablePtr](const auto &entry) { return variablePtr == entry.first.get(); };

    auto end = impl->m_VariableToPlotMultiMap.cend();
    auto it = std::find_if(impl->m_VariableToPlotMultiMap.cbegin(), end, findVariable);
    return it != end;
}

QString VisualizationGraphWidget::name() const
{
    return impl->m_Name;
}

QMimeData *VisualizationGraphWidget::mimeData(const QPoint &position) const
{
    auto mimeData = new QMimeData;

    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(position, plot());
    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones
        && selectionZoneItemUnderCursor) {
        mimeData->setData(MIME_TYPE_TIME_RANGE, TimeController::mimeDataForTimeRange(
                                                    selectionZoneItemUnderCursor->range()));
        mimeData->setData(MIME_TYPE_SELECTION_ZONE, TimeController::mimeDataForTimeRange(
                                                        selectionZoneItemUnderCursor->range()));
    }
    else {
        mimeData->setData(MIME_TYPE_GRAPH, QByteArray{});

        auto timeRangeData = TimeController::mimeDataForTimeRange(graphRange());
        mimeData->setData(MIME_TYPE_TIME_RANGE, timeRangeData);
    }

    return mimeData;
}

QPixmap VisualizationGraphWidget::customDragPixmap(const QPoint &dragPosition)
{
    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(dragPosition, plot());
    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones
        && selectionZoneItemUnderCursor) {

        auto zoneTopLeft = selectionZoneItemUnderCursor->topLeft->pixelPosition();
        auto zoneBottomRight = selectionZoneItemUnderCursor->bottomRight->pixelPosition();

        auto zoneSize = QSizeF{qAbs(zoneBottomRight.x() - zoneTopLeft.x()),
                               qAbs(zoneBottomRight.y() - zoneTopLeft.y())}
                            .toSize();

        auto pixmap = QPixmap(zoneSize);
        render(&pixmap, QPoint(), QRegion{QRect{zoneTopLeft.toPoint(), zoneSize}});

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
    if (highlighted) {
        plot().setBackground(QBrush(QColor("#BBD5EE")));
    }
    else {
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

void VisualizationGraphWidget::closeEvent(QCloseEvent *event)
{
    Q_UNUSED(event);

    // Prevents that all variables will be removed from graph when it will be closed
    for (auto &variableEntry : impl->m_VariableToPlotMultiMap) {
        emit variableAboutToBeRemoved(variableEntry.first);
    }
}

void VisualizationGraphWidget::enterEvent(QEvent *event)
{
    Q_UNUSED(event);
    impl->m_RenderingDelegate->showGraphOverlay(true);
}

void VisualizationGraphWidget::leaveEvent(QEvent *event)
{
    Q_UNUSED(event);
    impl->m_RenderingDelegate->showGraphOverlay(false);

    if (auto parentZone = parentZoneWidget()) {
        parentZone->notifyMouseLeaveGraph(this);
    }
    else {
        qCWarning(LOG_VisualizationGraphWidget()) << "leaveEvent: No parent zone widget";
    }

    if (impl->m_HoveredZone) {
        impl->m_HoveredZone->setHovered(false);
        impl->m_HoveredZone = nullptr;
    }
}

QCustomPlot &VisualizationGraphWidget::plot() const noexcept
{
    return *ui->widget;
}

void VisualizationGraphWidget::onGraphMenuRequested(const QPoint &pos) noexcept
{
    QMenu graphMenu{};

    // Iterates on variables (unique keys)
    for (auto it = impl->m_VariableToPlotMultiMap.cbegin(),
              end = impl->m_VariableToPlotMultiMap.cend();
         it != end; it = impl->m_VariableToPlotMultiMap.upper_bound(it->first)) {
        // 'Remove variable' action
        graphMenu.addAction(tr("Remove variable %1").arg(it->first->name()),
                            [ this, var = it->first ]() { removeVariable(var); });
    }

    if (!impl->m_ZoomStack.isEmpty()) {
        if (!graphMenu.isEmpty()) {
            graphMenu.addSeparator();
        }

        graphMenu.addAction(tr("Undo Zoom"), [this]() { undoZoom(); });
    }

    auto selectionZoneItem = impl->selectionZoneAt(pos, plot());
    if (selectionZoneItem) {
        auto selectedItems = parentVisualizationWidget()->selectionZoneManager().selectedItems();
        selectedItems.removeAll(selectionZoneItem);
        selectedItems.prepend(selectionZoneItem); // Put the current selection zone first

        auto zoneActions = sqpApp->actionsGuiController().selectionZoneActions();
        if (!zoneActions.isEmpty() && !graphMenu.isEmpty()) {
            graphMenu.addSeparator();
        }

        for (auto zoneAction : zoneActions) {
            auto action = graphMenu.addAction(zoneAction->name());
            action->setEnabled(zoneAction->isEnabled(selectedItems));
            action->setShortcut(zoneAction->displayedShortcut());
            QObject::connect(action, &QAction::triggered,
                             [zoneAction, selectedItems]() { zoneAction->execute(selectedItems); });
        }
    }

    if (!graphMenu.isEmpty()) {
        graphMenu.exec(QCursor::pos());
    }
}

void VisualizationGraphWidget::onRangeChanged(const QCPRange &t1, const QCPRange &t2)
{
    qCDebug(LOG_VisualizationGraphWidget())
        << tr("TORM: VisualizationGraphWidget::onRangeChanged")
        << QThread::currentThread()->objectName() << "DoAcqui" << impl->m_DoAcquisition;

    auto graphRange = SqpRange{t1.lower, t1.upper};
    auto oldGraphRange = SqpRange{t2.lower, t2.upper};

    if (impl->m_DoAcquisition) {
        QVector<std::shared_ptr<Variable> > variableUnderGraphVector;

        for (auto it = impl->m_VariableToPlotMultiMap.begin(),
                  end = impl->m_VariableToPlotMultiMap.end();
             it != end; it = impl->m_VariableToPlotMultiMap.upper_bound(it->first)) {
            variableUnderGraphVector.push_back(it->first);
        }
        emit requestDataLoading(std::move(variableUnderGraphVector), graphRange,
                                !impl->m_IsCalibration);

        if (!impl->m_IsCalibration) {
            qCDebug(LOG_VisualizationGraphWidget())
                << tr("TORM: VisualizationGraphWidget::Synchronize notify !!")
                << QThread::currentThread()->objectName() << graphRange << oldGraphRange;
            emit synchronize(graphRange, oldGraphRange);
        }
    }

    auto pos = mapFromGlobal(QCursor::pos());
    auto axisPos = impl->posToAxisPos(pos, plot());
    if (auto parentZone = parentZoneWidget()) {
        if (impl->pointIsInAxisRect(axisPos, plot())) {
            parentZone->notifyMouseMoveInGraph(pos, axisPos, this);
        }
        else {
            parentZone->notifyMouseLeaveGraph(this);
        }
    }
    else {
        qCWarning(LOG_VisualizationGraphWidget()) << "onMouseMove: No parent zone widget";
    }
}

void VisualizationGraphWidget::onMouseDoubleClick(QMouseEvent *event) noexcept
{
    impl->m_RenderingDelegate->onMouseDoubleClick(event);
}

void VisualizationGraphWidget::onMouseMove(QMouseEvent *event) noexcept
{
    // Handles plot rendering when mouse is moving
    impl->m_RenderingDelegate->onMouseMove(event);

    auto axisPos = impl->posToAxisPos(event->pos(), plot());

    // Zoom box and zone drawing
    if (impl->m_DrawingZoomRect) {
        impl->m_DrawingZoomRect->bottomRight->setCoords(axisPos);
    }
    else if (impl->m_DrawingZone) {
        impl->m_DrawingZone->setEnd(axisPos.x());
    }

    // Cursor
    if (auto parentZone = parentZoneWidget()) {
        if (impl->pointIsInAxisRect(axisPos, plot())) {
            parentZone->notifyMouseMoveInGraph(event->pos(), axisPos, this);
        }
        else {
            parentZone->notifyMouseLeaveGraph(this);
        }
    }
    else {
        qCWarning(LOG_VisualizationGraphWidget()) << "onMouseMove: No parent zone widget";
    }

    // Search for the selection zone under the mouse
    auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos(), plot());
    if (selectionZoneItemUnderCursor && !impl->m_DrawingZone
        && sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones) {

        // Sets the appropriate cursor shape
        auto cursorShape = selectionZoneItemUnderCursor->curshorShapeForPosition(event->pos());
        setCursor(cursorShape);

        // Manages the hovered zone
        if (selectionZoneItemUnderCursor != impl->m_HoveredZone) {
            if (impl->m_HoveredZone) {
                impl->m_HoveredZone->setHovered(false);
            }
            selectionZoneItemUnderCursor->setHovered(true);
            impl->m_HoveredZone = selectionZoneItemUnderCursor;
            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }
    else {
        // There is no zone under the mouse or the interaction mode is not "selection zones"
        if (impl->m_HoveredZone) {
            impl->m_HoveredZone->setHovered(false);
            impl->m_HoveredZone = nullptr;
        }

        setCursor(Qt::ArrowCursor);
    }

    impl->m_HasMovedMouse = true;
    VisualizationDragWidget::mouseMoveEvent(event);
}

void VisualizationGraphWidget::onMouseWheel(QWheelEvent *event) noexcept
{
    auto value = event->angleDelta().x() + event->angleDelta().y();
    if (value != 0) {

        auto direction = value > 0 ? 1.0 : -1.0;
        auto isZoomX = event->modifiers().testFlag(HORIZONTAL_ZOOM_MODIFIER);
        auto isZoomY = event->modifiers().testFlag(VERTICAL_ZOOM_MODIFIER);
        impl->m_IsCalibration = event->modifiers().testFlag(VERTICAL_PAN_MODIFIER);

        auto zoomOrientations = QFlags<Qt::Orientation>{};
        zoomOrientations.setFlag(Qt::Horizontal, isZoomX);
        zoomOrientations.setFlag(Qt::Vertical, isZoomY);

        ui->widget->axisRect()->setRangeZoom(zoomOrientations);

        if (!isZoomX && !isZoomY) {
            auto axis = plot().axisRect()->axis(QCPAxis::atBottom);
            auto diff = direction * (axis->range().size() * (PAN_SPEED / 100.0));

            axis->setRange(axis->range() + diff);

            if (plot().noAntialiasingOnDrag()) {
                plot().setNotAntialiasedElements(QCP::aeAll);
            }

            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }
}

void VisualizationGraphWidget::onMousePress(QMouseEvent *event) noexcept
{
    auto isDragDropClick = event->modifiers().testFlag(DRAG_DROP_MODIFIER);
    auto isSelectionZoneMode
        = sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones;
    auto isLeftClick = event->buttons().testFlag(Qt::LeftButton);

    if (!isDragDropClick && isLeftClick) {
        if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::ZoomBox) {
            // Starts a zoom box
            impl->startDrawingRect(event->pos(), plot());
        }
        else if (isSelectionZoneMode && impl->m_DrawingZone == nullptr) {
            // Starts a new selection zone
            auto zoneAtPos = impl->selectionZoneAt(event->pos(), plot());
            if (!zoneAtPos) {
                impl->startDrawingZone(event->pos(), this);
            }
        }
    }

    // Allows mouse panning only in default mode
    plot().setInteraction(QCP::iRangeDrag, sqpApp->plotsInteractionMode()
                                                   == SqpApplication::PlotsInteractionMode::None
                                               && !isDragDropClick);

    // Allows zone edition only in selection zone mode without drag&drop
    impl->setSelectionZonesEditionEnabled(isSelectionZoneMode && !isDragDropClick);

    // Selection / Deselection
    if (isSelectionZoneMode) {
        auto isMultiSelectionClick = event->modifiers().testFlag(MULTI_ZONE_SELECTION_MODIFIER);
        auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos(), plot());
        if (selectionZoneItemUnderCursor && isLeftClick) {
            selectionZoneItemUnderCursor->setAssociatedEditedZones(
                parentVisualizationWidget()->selectionZoneManager().selectedItems());
        }
        else if (!isMultiSelectionClick && isLeftClick) {
            parentVisualizationWidget()->selectionZoneManager().clearSelection();
        }
        else {
            // No selection change
        }
    }


    impl->m_HasMovedMouse = false;
    VisualizationDragWidget::mousePressEvent(event);
}

void VisualizationGraphWidget::onMouseRelease(QMouseEvent *event) noexcept
{
    if (impl->m_DrawingZoomRect) {

        auto axisX = plot().axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot().axisRect()->axis(QCPAxis::atLeft);

        auto newAxisXRange = QCPRange{impl->m_DrawingZoomRect->topLeft->coords().x(),
                                      impl->m_DrawingZoomRect->bottomRight->coords().x()};

        auto newAxisYRange = QCPRange{impl->m_DrawingZoomRect->topLeft->coords().y(),
                                      impl->m_DrawingZoomRect->bottomRight->coords().y()};

        impl->removeDrawingRect(plot());

        if (newAxisXRange.size() > axisX->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)
            && newAxisYRange.size() > axisY->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)) {
            impl->m_ZoomStack.push(qMakePair(axisX->range(), axisY->range()));
            axisX->setRange(newAxisXRange);
            axisY->setRange(newAxisYRange);

            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }

    impl->endDrawingZone(this);

    impl->m_IsCalibration = false;

    // Selection / Deselection
    auto isSelectionZoneMode
        = sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::SelectionZones;
    if (isSelectionZoneMode) {
        auto isMultiSelectionClick = event->modifiers().testFlag(MULTI_ZONE_SELECTION_MODIFIER);
        auto selectionZoneItemUnderCursor = impl->selectionZoneAt(event->pos(), plot());
        if (selectionZoneItemUnderCursor && event->button() == Qt::LeftButton) {
            if (!isMultiSelectionClick && !impl->m_HasMovedMouse) {
                parentVisualizationWidget()->selectionZoneManager().select(
                    {selectionZoneItemUnderCursor});
            }
            else if (!impl->m_HasMovedMouse) {
                parentVisualizationWidget()->selectionZoneManager().setSelected(
                    selectionZoneItemUnderCursor, !selectionZoneItemUnderCursor->selected()
                                                      || event->button() == Qt::RightButton);
            }
        }
        else {
            // No selection change
        }
    }
}

void VisualizationGraphWidget::onDataCacheVariableUpdated()
{
    auto graphRange = ui->widget->xAxis->range();
    auto dateTime = SqpRange{graphRange.lower, graphRange.upper};

    for (auto &variableEntry : impl->m_VariableToPlotMultiMap) {
        auto variable = variableEntry.first;
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated S" << variable->range();
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated E" << dateTime;
        if (dateTime.contains(variable->range()) || dateTime.intersect(variable->range())) {
            impl->updateData(variableEntry.second, variable->dataSeries(), variable->range());
        }
    }
}

void VisualizationGraphWidget::onUpdateVarDisplaying(std::shared_ptr<Variable> variable,
                                                     const SqpRange &range)
{
    auto it = impl->m_VariableToPlotMultiMap.find(variable);
    if (it != impl->m_VariableToPlotMultiMap.end()) {
        impl->updateData(it->second, variable->dataSeries(), range);
    }
}
