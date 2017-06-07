#include "visualization\VisualizationTabWidget.h"
#include "ui_VisualizationTabWidget.h"

VisualizationTabWidget::VisualizationTabWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::VisualizationTabWidget)
{
    ui->setupUi(this);
}

VisualizationTabWidget::~VisualizationTabWidget()
{
    delete ui;
}
