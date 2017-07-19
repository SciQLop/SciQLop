#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationGraphHelper.h"
#include "ui_VisualizationGraphWidget.h"

#include <Data/ArrayData.h>
#include <Data/IDataSeries.h>
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

} // namespace

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate {

    // 1 variable -> n qcpplot
    std::multimap<std::shared_ptr<Variable>, QCPAbstractPlottable *> m_VariableToPlotMultiMap;
};

VisualizationGraphWidget::VisualizationGraphWidget(const QString &name, QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationGraphWidget},
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>()}
{
    ui->setupUi(this);

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
    connect(ui->widget, &QCustomPlot::mouseWheel, this, &VisualizationGraphWidget::onMouseWheel);
    connect(ui->widget->xAxis,
            static_cast<void (QCPAxis::*)(const QCPRange &)>(&QCPAxis::rangeChanged), this,
            &VisualizationGraphWidget::onRangeChanged);

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

    // add 10% tolerance for each side
    auto tolerance = 0.1 * (dateTime.m_TEnd - dateTime.m_TStart);
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

void VisualizationGraphWidget::onRangeChanged(const QCPRange &t1)
{
    qCInfo(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::onRangeChanged")
                                           << QThread::currentThread()->objectName();

    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {

        auto variable = it->first;
        auto dateTime = SqpDateTime{t1.lower, t1.upper};
        auto dateTimeRange = dateTime;

        auto tolerance = 0.2 * (dateTime.m_TEnd - dateTime.m_TStart);
        auto variableDateTimeWithTolerance = dateTime;
        variableDateTimeWithTolerance.m_TStart -= tolerance;
        variableDateTimeWithTolerance.m_TEnd += tolerance;

        qCInfo(LOG_VisualizationGraphWidget()) << "v" << dateTime;
        qCInfo(LOG_VisualizationGraphWidget()) << "vtol" << variableDateTimeWithTolerance;
        // If new range with tol is upper than variable datetime parameters. we need to request new
        // data
        if (!variable->contains(variableDateTimeWithTolerance)) {

            auto variableDateTimeWithTolerance = dateTime;
            if (!variable->isInside(dateTime)) {
                auto variableDateTime = variable->dateTime();
                if (variableDateTime.m_TStart < dateTime.m_TStart) {
                    qCInfo(LOG_VisualizationGraphWidget()) << tr("TORM: Detection pan to right:");

                    auto diffEndToKeepDelta = dateTime.m_TEnd - variableDateTime.m_TEnd;
                    dateTime.m_TStart = variableDateTime.m_TStart + diffEndToKeepDelta;
                    // Tolerance have to be added to the right
                    // add 10% tolerance for right (end) side
                    //                    auto tolerance = 0.1 * (dateTime.m_TEnd -
                    //                    dateTime.m_TStart);
                    variableDateTimeWithTolerance.m_TEnd += tolerance;
                }
                else if (variableDateTime.m_TEnd > dateTime.m_TEnd) {
                    qCInfo(LOG_VisualizationGraphWidget()) << tr("TORM: Detection pan to left: ");
                    auto diffStartToKeepDelta = variableDateTime.m_TStart - dateTime.m_TStart;
                    dateTime.m_TEnd = variableDateTime.m_TEnd - diffStartToKeepDelta;
                    // Tolerance have to be added to the left
                    // add 10% tolerance for left (start) side
                    tolerance = 0.2 * (dateTime.m_TEnd - dateTime.m_TStart);
                    variableDateTimeWithTolerance.m_TStart -= tolerance;
                }
                else {
                    qCWarning(LOG_VisualizationGraphWidget())
                        << tr("Detection anormal zoom detection: ");
                }
            }
            else {
                qCInfo(LOG_VisualizationGraphWidget()) << tr("Detection zoom out: ");
                // add 10% tolerance for each side
                tolerance = 0.2 * (dateTime.m_TEnd - dateTime.m_TStart);
                variableDateTimeWithTolerance.m_TStart -= tolerance;
                variableDateTimeWithTolerance.m_TEnd += tolerance;
            }
            if (!variable->contains(dateTimeRange)) {
                qCInfo(LOG_VisualizationGraphWidget()) << "newv" << dateTime;
                variable->setDateTime(dateTime);
            }

            qCInfo(LOG_VisualizationGraphWidget()) << tr("Request data detection: ");
            // CHangement detected, we need to ask controller to request data loading
            emit requestDataLoading(variable, variableDateTimeWithTolerance);
        }
        else {
            qCInfo(LOG_VisualizationGraphWidget()) << tr("Detection zoom in: ");
        }
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
        qCInfo(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated S"
            << variable->dateTime();
        qCInfo(LOG_VisualizationGraphWidget())
            << "TORM: VisualizationGraphWidget::onDataCacheVariableUpdated E" << dateTime;
        if (dateTime.contains(variable->dateTime()) || dateTime.intersect(variable->dateTime())) {

            VisualizationGraphHelper::updateData(QVector<QCPAbstractPlottable *>{} << it->second,
                                                 variable->dataSeries(), variable->dateTime());
        }
    }
}

void VisualizationGraphWidget::updateDisplay(std::shared_ptr<Variable> variable)
{
    auto abstractPlotableItPair = impl->m_VariableToPlotMultiMap.equal_range(variable);

    auto abstractPlotableVect = QVector<QCPAbstractPlottable *>{};

    for (auto it = abstractPlotableItPair.first; it != abstractPlotableItPair.second; ++it) {
        abstractPlotableVect.push_back(it->second);
    }

    VisualizationGraphHelper::updateData(abstractPlotableVect, variable->dataSeries(),
                                         variable->dateTime());
}
