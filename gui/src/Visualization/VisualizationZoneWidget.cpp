#include "Visualization/VisualizationZoneWidget.h"
#include "ui_VisualizationZoneWidget.h"

#include "Visualization/VisualizationGraphWidget.h"

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

VisualizationGraphWidget *VisualizationZoneWidget::createGraph()
{
    auto graphWidget = new VisualizationGraphWidget{this};
    this->addGraph(graphWidget);

    return graphWidget;
}

void VisualizationZoneWidget::removeGraph(VisualizationGraphWidget *graph)
{
}

void VisualizationZoneWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
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
