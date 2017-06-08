#include <Variable/VariableInspectorWidget.h>

#include <ui_VariableInspectorWidget.h>

VariableInspectorWidget::VariableInspectorWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VariableInspectorWidget}
{
    ui->setupUi(this);
}

VariableInspectorWidget::~VariableInspectorWidget()
{
    delete ui;
}
