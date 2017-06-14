#include "Visualization/VisualizationTabWidget.h"
#include "ui_VisualizationTabWidget.h"

#include "Visualization/VisualizationZoneWidget.h"


VisualizationTabWidget::VisualizationTabWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VisualizationTabWidget}
{
    ui->setupUi(this);
}

VisualizationTabWidget::~VisualizationTabWidget()
{
    delete ui;
}

void VisualizationTabWidget::addZone(VisualizationZoneWidget *zoneWidget)
{
    this->layout()->addWidget(zoneWidget);
}

VisualizationZoneWidget *VisualizationTabWidget::createZone()
{
    auto zoneWidget = new VisualizationZoneWidget(this);
    this->addZone(zoneWidget);

    return zoneWidget;
}

void VisualizationTabWidget::removeZone(VisualizationZoneWidget *zone)
{
}

void VisualizationTabWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
}

void VisualizationTabWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationTabWidget::name() const
{
    return QStringLiteral("MainView");
}
