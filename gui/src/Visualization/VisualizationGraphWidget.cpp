#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/GraphPlottablesFactory.h"
#include "ui_VisualizationGraphWidget.h"

#include <Variable/Variable.h>

#include <unordered_map>

namespace {

/// Key pressed to enable zoom on horizontal axis
const auto HORIZONTAL_ZOOM_MODIFIER = Qt::NoModifier;

/// Key pressed to enable zoom on vertical axis
const auto VERTICAL_ZOOM_MODIFIER = Qt::ControlModifier;

} // namespace

struct VisualizationGraphWidget::VisualizationGraphWidgetPrivate {

    // 1 variable -> n qcpplot
    std::unordered_map<std::shared_ptr<Variable>, QCPAbstractPlottable *> m_VariableToPlotMap;
};

VisualizationGraphWidget::VisualizationGraphWidget(QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationGraphWidget},
          impl{spimpl::make_unique_impl<VisualizationGraphWidgetPrivate>()}
{
    ui->setupUi(this);

    // Set qcpplot properties :
    // - Drag (on x-axis) and zoom are enabled
    // - Mouse wheel on qcpplot is intercepted to determine the zoom orientation
    ui->widget->setInteractions(QCP::iRangeDrag | QCP::iRangeZoom);
    ui->widget->axisRect()->setRangeDrag(Qt::Horizontal);
    connect(ui->widget, &QCustomPlot::mouseWheel, this, &VisualizationGraphWidget::onMouseWheel);
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
        impl->m_VariableToPlotMap.insert({variable, createdPlottable});
    }
}

void VisualizationGraphWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
}

void VisualizationGraphWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationGraphWidget::name() const
{
    return QStringLiteral("MainView");
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
