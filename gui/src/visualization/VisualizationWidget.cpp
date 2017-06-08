#include "visualization/VisualizationWidget.h"
#include "ui_VisualizationWidget.h"

VisualizationWidget::VisualizationWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::VisualizationWidget)
{
    ui->setupUi(this);
}

VisualizationWidget::~VisualizationWidget()
{
    delete ui;
}
