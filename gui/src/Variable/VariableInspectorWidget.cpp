#include <Variable/VariableController.h>
#include <Variable/VariableInspectorWidget.h>
#include <Variable/VariableModel.h>

#include <ui_VariableInspectorWidget.h>

#include <QSortFilterProxyModel>

#include <SqpApplication.h>

Q_LOGGING_CATEGORY(LOG_VariableInspectorWidget, "VariableInspectorWidget")

VariableInspectorWidget::VariableInspectorWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VariableInspectorWidget}
{
    ui->setupUi(this);

    // Sets model for table
    auto sortFilterModel = new QSortFilterProxyModel{this};
    sortFilterModel->setSourceModel(sqpApp->variableController().variableModel());

    ui->tableView->setModel(sortFilterModel);

    // Fixes column sizes
    auto model = ui->tableView->model();
    const auto count = model->columnCount();
    for (auto i = 0; i < count; ++i) {
        ui->tableView->setColumnWidth(
            i, model->headerData(i, Qt::Horizontal, Qt::SizeHintRole).toSize().width());
    }

    // Sets selection options
    ui->tableView->setSelectionBehavior(QTableView::SelectRows);
    ui->tableView->setSelectionMode(QTableView::ExtendedSelection);

    // Connection to show a menu when right clicking on the tree
    ui->tableView->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->tableView, &QTableView::customContextMenuRequested, this,
            &VariableInspectorWidget::onTableMenuRequested);
}

VariableInspectorWidget::~VariableInspectorWidget()
{
    delete ui;
}

void VariableInspectorWidget::onTableMenuRequested(const QPoint &pos) noexcept
{
    auto selectedIndex = ui->tableView->indexAt(pos);
    if (selectedIndex.isValid()) {
        // Gets the model to retrieve the underlying selected variable
        auto model = sqpApp->variableController().variableModel();
        if (auto selectedVariable = model->variable(selectedIndex.row())) {
            QMenu tableMenu{};

            // Emit a signal so that potential receivers can populate the menu before displaying it
            emit tableMenuAboutToBeDisplayed(&tableMenu, selectedVariable);

            if (!tableMenu.isEmpty()) {
                tableMenu.exec(mapToGlobal(pos));
            }
        }
    }
    else {
        qCCritical(LOG_VariableInspectorWidget())
            << tr("Can't display menu : invalid index (%1;%2)")
                   .arg(selectedIndex.row(), selectedIndex.column());
    }
}
