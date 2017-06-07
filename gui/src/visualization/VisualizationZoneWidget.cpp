#include "visualization\VisualizationZoneWidget.h"
#include "ui_VisualizationZoneWidget.h"

VisualizationZoneWidget::VisualizationZoneWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::VisualizationZoneWidget)
{
    ui->setupUi(this);
}

VisualizationZoneWidget::~VisualizationZoneWidget()
{
    delete ui;
}
