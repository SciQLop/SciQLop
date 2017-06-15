#include <Variable/VariableController.h>
#include <Variable/VariableInspectorWidget.h>
#include <Variable/VariableModel.h>

#include <ui_VariableInspectorWidget.h>

#include <QSortFilterProxyModel>

#include <SqpApplication.h>

VariableInspectorWidget::VariableInspectorWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VariableInspectorWidget}
{
    ui->setupUi(this);

    // Sets model for table
    auto sortFilterModel = new QSortFilterProxyModel{this};
    sortFilterModel->setSourceModel(sqpApp->variableController().variableModel());

    ui->tableView->setModel(sortFilterModel);
}

VariableInspectorWidget::~VariableInspectorWidget()
{
    delete ui;
}
