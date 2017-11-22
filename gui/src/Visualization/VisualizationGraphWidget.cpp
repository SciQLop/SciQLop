#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationCursorItem.h"
#include "Visualization/VisualizationDefs.h"
#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "Visualization/VisualizationZoneWidget.h"
#include "ui_VisualizationGraphWidget.h"

#include <Common/MimeTypesDef.h>
#include <Data/ArrayData.h>
#include <Data/IDataSeries.h>
#include <DragAndDrop/DragDropHelper.h>
#include <Settings/SqpSettingsDefs.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphWidget, "VisualizationGraphWidget")

namespace {

/// Key pressed to enable zoom on horizontal axis
const auto HORIZONTAL_ZOOM_MODIFIER = Qt::ControlModifier;

/// Key pressed to enable zoom on vertical axis
const auto VERTICAL_ZOOM_MODIFIER = Qt::ShiftModifier;

/// Speed of a step of a wheel event for a pan, in percentage of the axis range
const auto PAN_SPEED = 5;

/// Key pressed to enable a calibration pan
const auto VERTICAL_PAN_MODIFIER = Qt::AltModifier;

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

    QString m_Name;
    // 1 variable -> n qcpplot
    std::map<std::shared_ptr<Variable>, PlottablesMap> m_VariableToPlotMultiMap;
    bool m_DoAcquisition;
    bool m_IsCalibration;
    /// Delegate used to attach rendering features to the plot
    std::unique_ptr<VisualizationGraphRenderingDelegate> m_RenderingDelegate;

    QCPItemRect *m_DrawingRect = nullptr;
    std::unique_ptr<VisualizationCursorItem> m_HorizontalCursor = nullptr;
    std::unique_ptr<VisualizationCursorItem> m_VerticalCursor = nullptr;

    void configureDrawingRect()
    {
        if (m_DrawingRect) {
            QPen p;
            p.setWidth(2);
            m_DrawingRect->setPen(p);
        }
    }

    void startDrawingRect(const QPoint &pos, QCustomPlot &plot)
    {
        removeDrawingRect(plot);

        auto axisPos = posToAxisPos(pos, plot);

        m_DrawingRect = new QCPItemRect{&plot};
        configureDrawingRect();

        m_DrawingRect->topLeft->setCoords(axisPos);
        m_DrawingRect->bottomRight->setCoords(axisPos);
    }

    void removeDrawingRect(QCustomPlot &plot)
    {
        if (m_DrawingRect) {
            plot.removeItem(m_DrawingRect); // the item is deleted by QCustomPlot
            m_DrawingRect = nullptr;
            plot.replot(QCustomPlot::rpQueuedReplot);
        }
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
    // - Drag (on x-axis) and zoom are enabled
    // - Mouse wheel on qcpplot is intercepted to determine the zoom orientation
    ui->widget->setInteractions(QCP::iRangeZoom | QCP::iSelectItems);

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
    connect(ui->widget->xAxis, static_cast<void (QCPAxis::*)(const QCPRange &, const QCPRange &)>(
                                   &QCPAxis::rangeChanged),
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
    /// @todo : for the moment, a graph can always accomodate a variable
    Q_UNUSED(variable);
    return true;
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

QMimeData *VisualizationGraphWidget::mimeData() const
{
    auto mimeData = new QMimeData;
    mimeData->setData(MIME_TYPE_GRAPH, QByteArray{});

    auto timeRangeData = TimeController::mimeDataForTimeRange(graphRange());
    mimeData->setData(MIME_TYPE_TIME_RANGE, timeRangeData);

    return mimeData;
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
}

QCustomPlot &VisualizationGraphWidget::plot() noexcept
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

    if (!graphMenu.isEmpty()) {
        graphMenu.exec(QCursor::pos());
    }
}

void VisualizationGraphWidget::onRangeChanged(const QCPRange &t1, const QCPRange &t2)
{
    qCDebug(LOG_VisualizationGraphWidget()) << tr("TORM: VisualizationGraphWidget::onRangeChanged")
                                            << QThread::currentThread()->objectName() << "DoAcqui"
                                            << impl->m_DoAcquisition;

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

void VisualizationGraphWidget::onMouseMove(QMouseEvent *event) noexcept
{
    // Handles plot rendering when mouse is moving
    impl->m_RenderingDelegate->onMouseMove(event);

    auto axisPos = impl->posToAxisPos(event->pos(), plot());

    if (impl->m_DrawingRect) {
        impl->m_DrawingRect->bottomRight->setCoords(axisPos);
    }

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
    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::ZoomBox) {
        impl->startDrawingRect(event->pos(), plot());
    }

    VisualizationDragWidget::mousePressEvent(event);
}

void VisualizationGraphWidget::onMouseRelease(QMouseEvent *event) noexcept
{
    if (impl->m_DrawingRect) {

        auto axisX = plot().axisRect()->axis(QCPAxis::atBottom);
        auto axisY = plot().axisRect()->axis(QCPAxis::atLeft);

        auto newAxisXRange = QCPRange{impl->m_DrawingRect->topLeft->coords().x(),
                                      impl->m_DrawingRect->bottomRight->coords().x()};

        auto newAxisYRange = QCPRange{impl->m_DrawingRect->topLeft->coords().y(),
                                      impl->m_DrawingRect->bottomRight->coords().y()};

        impl->removeDrawingRect(plot());

        if (newAxisXRange.size() > axisX->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)
            && newAxisYRange.size() > axisY->range().size() * (ZOOM_BOX_MIN_SIZE / 100.0)) {
            axisX->setRange(newAxisXRange);
            axisY->setRange(newAxisYRange);

            plot().replot(QCustomPlot::rpQueuedReplot);
        }
    }

    impl->m_IsCalibration = false;
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
            VisualizationGraphHelper::updateData(variableEntry.second, variable->dataSeries(),
                                                 variable->range());
        }
    }
}

void VisualizationGraphWidget::onUpdateVarDisplaying(std::shared_ptr<Variable> variable,
                                                     const SqpRange &range)
{
    auto it = impl->m_VariableToPlotMultiMap.find(variable);
    if (it != impl->m_VariableToPlotMultiMap.end()) {
        VisualizationGraphHelper::updateData(it->second, variable->dataSeries(), range);
    }
}
