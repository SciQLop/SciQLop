#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/GraphPlottablesFactory.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
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
    auto createdPlottables = GraphPlottablesFactory::create(variable, *ui->widget);

    for (auto createdPlottable : qAsConst(createdPlottables)) {
        impl->m_VariableToPlotMultiMap.insert({variable, createdPlottable});
    }

    connect(variable.get(), &Variable::dataCacheUpdated, this,
            &VisualizationGraphWidget::onDataCacheVariableUpdated);
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
        auto tolerance = 0.1 * (t2.upper - t2.lower);
        auto dateTime = SqpDateTime{t2.lower - tolerance, t2.upper + tolerance};

        qCInfo(LOG_VisualizationGraphWidget()) << tr("VisualizationGraphWidget::onRangeChanged")
                                               << variable->dataSeries()->xAxisData()->size();
        if (!variable->contains(dateTime)) {
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
    for (auto it = impl->m_VariableToPlotMultiMap.cbegin();
         it != impl->m_VariableToPlotMultiMap.cend(); ++it) {
        auto variable = it->first;
        GraphPlottablesFactory::updateData(QVector<QCPAbstractPlottable *>{} << it->second,
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

    GraphPlottablesFactory::updateData(abstractPlotableVect, variable->dataSeries(),
                                       variable->dateTime());
}
