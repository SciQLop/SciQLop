#include "Visualization/VisualizationZoneWidget.h"
#include "ui_VisualizationZoneWidget.h"

#include "Visualization/VisualizationGraphWidget.h"

VisualizationZoneWidget::VisualizationZoneWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VisualizationZoneWidget}
{
    ui->setupUi(this);
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
    auto graphWidget = new VisualizationGraphWidget(this);
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

QString VisualizationZoneWidget::name()
{
    return QStringLiteral("MainView");
}
