#include "Visualization/VisualizationGraphWidget.h"
#include "ui_VisualizationGraphWidget.h"

VisualizationGraphWidget::VisualizationGraphWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::VisualizationGraphWidget)
{
    ui->setupUi(this);
}

VisualizationGraphWidget::~VisualizationGraphWidget()
{
    delete ui;
}
