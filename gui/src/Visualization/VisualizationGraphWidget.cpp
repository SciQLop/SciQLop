#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationGraphHelper.h"
#include "Visualization/VisualizationGraphRenderingDelegate.h"
#include "ui_VisualizationGraphWidget.h"

#include <Data/ArrayData.h>
#include <Data/IDataSeries.h>
#include <Settings/SqpSettingsDefs.h>
#include <SqpApplication.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <unordered_map>

Q_LOGGING_CATEGORY(LOG_VisualizationGraphWidget, "VisualizationGraphWidget")

namespace {

/// Key pressed to enable zoom on horizontal axis
const auto HORIZONTAL_ZOOM_MODIFIER = Qt::NoModifier;

/// Key pressed to enable zoom on vertical axis
const auto VERTICAL_ZOOM_MODIFIER = Qt::ControlModifier;

/// Gets a tolerance value from application settings. If the setting can't be found, the default
/// value passed in parameter is returned
double toleranceValue(const QString &key, double defaultValue) noexcept
{
    return QSettings{}.value(key, defaultValue).toDouble();
}

} // namespace

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate {

    explicit VisualizationGraphWidgetPrivate()
            : m_DoSynchronize{true}, m_IsCalibration{false}, m_RenderingDelegate{nullptr}
    {
    }

    // Return the operation when range changed
    VisualizationGraphWidgetZoomType getZoomType(const QCPRange &t1, const QCPRange &t2);

    // 1 variable -> n qcpplot
    std::multimap<std::shared_ptr<Variable>, QCPAbstractPlottable *> m_VariableToPlotMultiMap;
    bool m_DoSynchronize;
    bool m_IsCalibration;
    QCPItemTracer *m_TextTracer;
    /// Delegate used to attach rendering features to the plot
    std::unique_ptr<VisualizationGraphRenderingDelegate> m_RenderingDelegate;
};

VisualizationGraphWidget::VisualizationGraphWidget(const QString &name, QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationGraphWidget},
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>()}
{
    ui->setupUi(this);

    // The delegate must be initialized after the ui as it uses the plot
    impl->m_RenderingDelegate = std::make_unique<VisualizationGraphRenderingDelegate>(*ui->widget);

    ui->graphNameLabel->setText(name);

    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
    connect(ui->closeButton, &QToolButton::clicked, this, &VisualizationGraphWidget::close);
    ui->closeButton->setIcon(sqpApp->style()->standardIcon(QStyle::SP_TitleBarCloseButton));

    // Set qcpplot properties :
    // - Drag (on x-axis) and zoom are enabled
    // - Mouse wheel on qcpplot is intercepted to determine the zoom orientation
    ui->widget->setInteractions(QCP::iRangeDrag | QCP::iRangeZoom);
    ui->widget->axisRect()->setRangeDrag(Qt::Horizontal);
    connect(ui->widget, &QCustomPlot::mousePress, this, &VisualizationGraphWidget::onMousePress);
    connect(ui->widget, &QCustomPlot::mouseRelease, this,
            &VisualizationGraphWidget::onMouseRelease);
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
}


VisualizationGraphWidget::~VisualizationGraphWidget()
{
    delete ui;
}

void VisualizationGraphWidget::enableSynchronize(bool enable)
{
    impl->m_DoSynchronize = enable;
}

void VisualizationGraphWidget::addVariable(std::shared_ptr<Variable> variable)
{
    // Uses delegate to create the qcpplot components according to the variable
    auto createdPlottables = VisualizationGraphHelper::create(variable, *ui->widget);

    for (auto createdPlottable : qAsConst(createdPlottables)) {
        impl->m_VariableToPlotMultiMap.insert({variable, createdPlottable});
    }

    connect(variable.get(), SIGNAL(updated()), this, SLOT(onDataCacheVariableUpdated()));
}
void VisualizationGraphWidget::addVariableUsingGraph(std::shared_ptr<Variable> variable)
{

    // when adding a variable, we need to set its time range to the current graph range
    auto grapheRange = ui->widget->xAxis->range();
    auto dateTime = SqpDateTime{grapheRange.lower, grapheRange.upper};
    variable->setDateTime(dateTime);

    auto variableDateTimeWithTolerance = dateTime;

    // add tolerance for each side
    auto toleranceFactor
        = toleranceValue(GENERAL_TOLERANCE_AT_INIT_KEY, GENERAL_TOLERANCE_AT_INIT_DEFAULT_VALUE);
    auto tolerance = toleranceFactor * (dateTime.m_TEnd - dateTime.m_TStart);
    variableDateTimeWithTolerance.m_TStart -= tolerance;
    variableDateTimeWithTolerance.m_TEnd += tolerance;

    // Uses delegate to create the qcpplot components according to the variable
    auto createdPlottables = VisualizationGraphHelper::create(variable, *ui->widget);

    for (auto createdPlottable : qAsConst(createdPlottables)) {
        impl->m_VariableToPlotMultiMap.insert({variable, createdPlottable});
    }

    connect(variable.get(), SIGNAL(updated()), this, SLOT(onDataCacheVariableUpdated()));

    // CHangement detected, we need to ask controller to request data loading
    emit requestDataLoading(variable, variableDateTimeWithTolerance);
}

void VisualizationGraphWidget::removeVariable(std::shared_ptr<Variable> variable) noexcept
{
    // Each component associated to the variable :
    // - is removed from qcpplot (which deletes it)
    // - is no longer referenced in the map
    auto componentsIt = impl->m_VariableToPlotMultiMap.equal_range(variable);
    for (auto it = componentsIt.first; it != componentsIt.second;) {
        ui->widget->removePlottable(it->second);
        it = impl->m_VariableToPlotMultiMap.erase(it);
    }

    // Updates graph
    ui->widget->replot();
}

void VisualizationGraphWidget::setRange(std::shared_ptr<Variable> variable,
                                        const SqpDateTime &range)
{
    // Note: in case of different axes that depends on variable, we could start with a code like
    // that:
    //    auto componentsIt = impl->m_VariableToPlotMultiMap.equal_range(variable);
    //    for (auto it = componentsIt.first; it != componentsIt.second;) {
    //    }
    ui->widget->xAxis->setRange(range.m_TStart, range.m_TEnd);
    ui->widget->replot();
}

SqpDateTime VisualizationGraphWidget::graphRange() const noexcept
{
    auto grapheRange = ui->widget->xAxis->range();
    return SqpDateTime{grapheRange.lower, grapheRange.upper};
}

void VisualizationGraphWidget::setGraphRange(const SqpDateTime &range)
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
    return ui->graphNameLabel->text();
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
        graphMenu.exec(mapToGlobal(pos));
    }
}

void VisualizationGraphWidget::onRangeChanged(const QCPRange &t1, const QCPRange &t2)
{
    qCInfo(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::onRangeChanged")
                                           << QThread::currentThread()->objectName();

    auto dateTimeRange = SqpDateTime{t1.lower, t1.upper};

    auto zoomType = impl->getZoomType(t1, t2);
    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {

        auto variable = it->first;
        auto currentDateTime = dateTimeRange;

        auto toleranceFactor = toleranceValue(GENERAL_TOLERANCE_AT_UPDATE_KEY,
                                              GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE);
        auto tolerance = toleranceFactor * (currentDateTime.m_TEnd - currentDateTime.m_TStart);
        auto variableDateTimeWithTolerance = currentDateTime;
        variableDateTimeWithTolerance.m_TStart -= tolerance;
        variableDateTimeWithTolerance.m_TEnd += tolerance;

        qCDebug(LOG_VisualizationGraphWidget()) << "r" << currentDateTime;
        qCDebug(LOG_VisualizationGraphWidget()) << "t" << variableDateTimeWithTolerance;
        qCDebug(LOG_VisualizationGraphWidget()) << "v" << variable->dateTime();
        // If new range with tol is upper than variable datetime parameters. we need to request new
        // data
        if (!variable->contains(variableDateTimeWithTolerance)) {

            auto variableDateTimeWithTolerance = currentDateTime;
            if (!variable->isInside(currentDateTime)) {
                auto variableDateTime = variable->dateTime();
                if (variable->contains(variableDateTimeWithTolerance)) {
                    qCDebug(LOG_VisualizationGraphWidget())
                        << tr("TORM: Detection zoom in that need request:");
                    // add tolerance for each side
                    tolerance
                        = toleranceFactor * (currentDateTime.m_TEnd - currentDateTime.m_TStart);
                    variableDateTimeWithTolerance.m_TStart -= tolerance;
                    variableDateTimeWithTolerance.m_TEnd += tolerance;
                }
                else if (variableDateTime.m_TStart < currentDateTime.m_TStart) {
                    qCInfo(LOG_VisualizationGraphWidget()) << tr("TORM: Detection pan to right:");

                    auto diffEndToKeepDelta = currentDateTime.m_TEnd - variableDateTime.m_TEnd;
                    currentDateTime.m_TStart = variableDateTime.m_TStart + diffEndToKeepDelta;
                    // Tolerance have to be added to the right
                    // add tolerance for right (end) side
                    tolerance
                        = toleranceFactor * (currentDateTime.m_TEnd - currentDateTime.m_TStart);
                    variableDateTimeWithTolerance.m_TEnd += tolerance;
                }
                else if (variableDateTime.m_TEnd > currentDateTime.m_TEnd) {
                    qCDebug(LOG_VisualizationGraphWidget()) << tr("TORM: Detection pan to left: ");
                    auto diffStartToKeepDelta
                        = variableDateTime.m_TStart - currentDateTime.m_TStart;
                    currentDateTime.m_TEnd = variableDateTime.m_TEnd - diffStartToKeepDelta;
                    // Tolerance have to be added to the left
                    // add tolerance for left (start) side
                    tolerance
                        = toleranceFactor * (currentDateTime.m_TEnd - currentDateTime.m_TStart);
                    variableDateTimeWithTolerance.m_TStart -= tolerance;
                }
                else {
                    qCCritical(LOG_VisualizationGraphWidget())
                        << tr("Detection anormal zoom detection: ");
                }
            }
            else {
                qCDebug(LOG_VisualizationGraphWidget()) << tr("TORM: Detection zoom out: ");
                // add tolerance for each side
                tolerance = toleranceFactor * (currentDateTime.m_TEnd - currentDateTime.m_TStart);
                variableDateTimeWithTolerance.m_TStart -= tolerance;
                variableDateTimeWithTolerance.m_TEnd += tolerance;
                zoomType = VisualizationGraphWidgetZoomType::ZoomOut;
            }
            if (!variable->contains(dateTimeRange)) {
                qCDebug(LOG_VisualizationGraphWidget())
                    << "TORM: Modif on variable datetime detected" << currentDateTime;
                variable->setDateTime(currentDateTime);
            }

            qCDebug(LOG_VisualizationGraphWidget()) << tr("TORM: Request data detection: ");
            // CHangement detected, we need to ask controller to request data loading
            emit requestDataLoading(variable, variableDateTimeWithTolerance);
        }
        else {
            qCInfo(LOG_VisualizationGraphWidget())
                << tr("TORM: Detection zoom in that doesn't need request: ");
            zoomType = VisualizationGraphWidgetZoomType::ZoomIn;
        }
    }

    if (impl->m_DoSynchronize && !impl->m_IsCalibration) {
        auto oldDateTime = SqpDateTime{t2.lower, t2.upper};
        qCDebug(LOG_VisualizationGraphWidget())
            << tr("TORM: VisualizationGraphWidget::Synchronize notify !!")
            << QThread::currentThread()->objectName();
        emit synchronize(dateTimeRange, oldDateTime, zoomType);
    }
}

void VisualizationGraphWidget::onMouseWheel(QWheelEvent *event) noexcept
{
    auto zoomOrientations = QFlags<Qt::Orientation>{};

    // Lambda that enables a zoom orientation if the key modifier related to this orientation
    // has
    // been pressed
    auto enableOrientation
        = [&zoomOrientations, event](const auto &orientation, const auto &modifier) {
              auto orientationEnabled = event->modifiers().testFlag(modifier);
              zoomOrientations.setFlag(orientation, orientationEnabled);
          };
    enableOrientation(Qt::Vertical, VERTICAL_ZOOM_MODIFIER);
    enableOrientation(Qt::Horizontal, HORIZONTAL_ZOOM_MODIFIER);

    ui->widget->axisRect()->setRangeZoom(zoomOrientations);
}

void VisualizationGraphWidget::onMousePress(QMouseEvent *event) noexcept
{
    impl->m_IsCalibration = event->modifiers().testFlag(Qt::ControlModifier);
}

void VisualizationGraphWidget::onMouseRelease(QMouseEvent *event) noexcept
{
    impl->m_IsCalibration = false;
}

void VisualizationGraphWidget::onDataCacheVariableUpdated()
{
    // NOTE:
    //    We don't want to call the method for each component of a variable unitarily, but for
    //    all
    //    its components at once (eg its three components in the case of a vector).

    //    The unordered_multimap does not do this easily, so the question is whether to:
    //    - use an ordered_multimap and the algos of std to group the values by key
    //    - use a map (unique keys) and store as values directly the list of components

    auto grapheRange = ui->widget->xAxis->range();
    auto dateTime = SqpDateTime{grapheRange.lower, grapheRange.upper};

    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {
        auto variable = it->first;
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated S"
            << variable->dateTime();
        qCDebug(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated E" << dateTime;
        if (dateTime.contains(variable->dateTime()) || dateTime.intersect(variable->dateTime())) {

            VisualizationGraphHelper::updateData(QVector<QCPAbstractPlottable *>{} << it->second,
                                                 variable->dataSeries(), variable->dateTime());
        }
    }
}

VisualizationGraphWidgetZoomType
VisualizationGraphWidget::VisualizationGraphWidgetPrivate::getZoomType(const QCPRange &t1,
                                                                       const QCPRange &t2)
{
    // t1.lower <= t2.lower && t2.upper <= t1.upper
    auto zoomType = VisualizationGraphWidgetZoomType::Unknown;
    if (t1.lower <= t2.lower && t2.upper <= t1.upper) {
        zoomType = VisualizationGraphWidgetZoomType::ZoomOut;
    }
    else if (t1.lower > t2.lower && t1.upper > t2.upper) {
        zoomType = VisualizationGraphWidgetZoomType::PanRight;
    }
    else if (t1.lower < t2.lower && t1.upper < t2.upper) {
        zoomType = VisualizationGraphWidgetZoomType::PanLeft;
    }
    else if (t1.lower > t2.lower && t2.upper > t1.upper) {
        zoomType = VisualizationGraphWidgetZoomType::ZoomIn;
    }
    else {
        qCCritical(LOG_VisualizationGraphWidget()) << "getZoomType: Unknown type detected";
    }
    return zoomType;
}
