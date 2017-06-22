#include "Visualization/VisualizationZoneWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "ui_VisualizationZoneWidget.h"

#include "Visualization/VisualizationGraphWidget.h"

namespace {

/// Generates a default name for a new graph, according to the number of graphs already displayed in
/// the zone
QString defaultGraphName(const QLayout &layout)
{
    auto count = 0;
    for (auto i = 0; i < layout.count(); ++i) {
        if (dynamic_cast<VisualizationGraphWidget *>(layout.itemAt(i)->widget())) {
            count++;
        }
    }

    return QObject::tr("Graph %1").arg(count + 1);
}

} // namespace

VisualizationZoneWidget::VisualizationZoneWidget(const QString &name, QWidget *parent)
        : QWidget{parent}, ui{new Ui::VisualizationZoneWidget}
{
    ui->setupUi(this);

    ui->zoneNameLabel->setText(name);
}

VisualizationZoneWidget::~VisualizationZoneWidget()
{
    delete ui;
}

void VisualizationZoneWidget::addGraph(VisualizationGraphWidget *graphWidget)
{
    ui->visualizationZoneFrame->layout()->addWidget(graphWidget);
}

VisualizationGraphWidget *VisualizationZoneWidget::createGraph(std::shared_ptr<Variable> variable)
{
    auto graphWidget = new VisualizationGraphWidget{
        defaultGraphName(*ui->visualizationZoneFrame->layout()), this};
    this->addGraph(graphWidget);

    graphWidget->addVariable(variable);

    return graphWidget;
}

void VisualizationZoneWidget::removeGraph(VisualizationGraphWidget *graph)
{
}

void VisualizationZoneWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor to graph children
        auto layout = ui->visualizationZoneFrame->layout();
        for (auto i = 0; i < layout->count(); ++i) {
            if (auto item = layout->itemAt(i)) {
                if (auto visualizationGraphWidget
                    = dynamic_cast<VisualizationGraphWidget *>(item->widget())) {
                    visualizationGraphWidget->accept(visitor);
                }
            }
        }

        visitor->visitLeave(this);
    }
}

bool VisualizationZoneWidget::canDrop(const Variable &variable) const
{
    // A tab can always accomodate a variable
    Q_UNUSED(variable);
    return true;
}

void VisualizationZoneWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationZoneWidget::name() const
{
    return ui->zoneNameLabel->text();
}
