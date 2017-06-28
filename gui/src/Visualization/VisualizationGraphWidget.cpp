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
    std::unordered_multimap<std::shared_ptr<Variable>, QCPAbstractPlottable *>
        m_VariableToPlotMultiMap;
};

VisualizationGraphWidget::VisualizationGraphWidget(const QString &name, QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationGraphWidget},
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>()}
{
    ui->setupUi(this);

    // qcpplot title
    ui->widget->plotLayout()->insertRow(0);
    ui->widget->plotLayout()->addElement(0, 0, new QCPTextElement{ui->widget, name});

    // Set qcpplot properties :
    // - Drag (on x-axis) and zoom are enabled
    // - Mouse wheel on qcpplot is intercepted to determine the zoom orientation
    ui->widget->setInteractions(QCP::iRangeDrag | QCP::iRangeZoom);
    ui->widget->axisRect()->setRangeDrag(Qt::Horizontal);
    connect(ui->widget, &QCustomPlot::mouseWheel, this, &VisualizationGraphWidget::onMouseWheel);
    connect(ui->widget->xAxis, static_cast<void (QCPAxis::*)(const QCPRange &, const QCPRange &)>(
                                   &QCPAxis::rangeChanged),
            this, &VisualizationGraphWidget::onRangeChanged);
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

    connect(variable.get(), SIGNAL(dataCacheUpdated()), this, SLOT(onDataCacheVariableUpdated()));
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

void VisualizationGraphWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationGraphWidget::name() const
{
    if (auto title = dynamic_cast<QCPTextElement *>(ui->widget->plotLayout()->elementAt(0))) {
        return title->text();
    }
    else {
        return QString{};
    }
}

void VisualizationGraphWidget::onRangeChanged(const QCPRange &t1, const QCPRange &t2)
{

    qCDebug(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::onRangeChanged");

    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {

        auto variable = it->first;
        qCInfo(LOG_VisualizationGraphWidget())
            << tr("TORM: VisualizationGraphWidget::onRangeChanged")
            << variable->dataSeries()->xAxisData()->size();
        auto dateTime = SqpDateTime{t2.lower, t2.upper};

        if (!variable->contains(dateTime)) {

            if (variable->intersect(dateTime)) {
                auto variableDateTime = variable->dateTime();
                if (variableDateTime.m_TStart < dateTime.m_TStart) {
                    dateTime.m_TStart = variableDateTime.m_TStart;
                    // add 20% tolerance for left (start) side
                    auto tolerance = 0.2 * (dateTime.m_TEnd - dateTime.m_TStart);
                    dateTime.m_TStart -= tolerance;
                }

                if (variableDateTime.m_TEnd > dateTime.m_TEnd) {
                    dateTime.m_TEnd = variableDateTime.m_TEnd;
                    // add 20% tolerance for right (end) side
                    auto tolerance = 0.2 * (dateTime.m_TEnd - dateTime.m_TStart);
                    dateTime.m_TEnd += tolerance;
                }
            }
            else {
                // add 10% tolerance for each side
                auto tolerance = 0.1 * (dateTime.m_TEnd - dateTime.m_TStart);
                dateTime.m_TStart -= tolerance;
                dateTime.m_TEnd += tolerance;
            }
            // CHangement detected, we need to
            sqpApp->variableController().requestDataLoading(variable, dateTime);
        }
    }
}

void VisualizationGraphWidget::onMouseWheel(QWheelEvent *event) noexcept
{
    auto zoomOrientations = QFlags<Qt::Orientation>{};

    // Lambda that enables a zoom orientation if the key modifier related to this orientation has
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
    //    We don't want to call the method for each component of a variable unitarily, but for all
    //    its components at once (eg its three components in the case of a vector).

    //    The unordered_multimap does not do this easily, so the question is whether to:
    //    - use an ordered_multimap and the algos of std to group the values by key
    //    - use a map (unique keys) and store as values directly the list of components

    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {
        auto variable = it->first;
        VisualizationGraphHelper::updateData(QVector<QCPAbstractPlottable *>{} << it->second,
                                             variable->dataSeries(), variable->dateTime());
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
