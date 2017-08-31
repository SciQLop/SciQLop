#include <Variable/VariableController.h>
#include <Variable/VariableInspectorWidget.h>
#include <Variable/VariableMenuHeaderWidget.h>
#include <Variable/VariableModel.h>

#include <ui_VariableInspectorWidget.h>

#include <QMouseEvent>
#include <QSortFilterProxyModel>
#include <QStyledItemDelegate>
#include <QWidgetAction>

#include <SqpApplication.h>

Q_LOGGING_CATEGORY(LOG_VariableInspectorWidget, "VariableInspectorWidget")


class QProgressBarItemDelegate : public QStyledItemDelegate {

public:
    QProgressBarItemDelegate(QObject *parent) : QStyledItemDelegate{parent} {}

    void paint(QPainter *painter, const QStyleOptionViewItem &option,
               const QModelIndex &index) const
    {
        auto data = index.data(Qt::DisplayRole);
        auto progressData = index.data(VariableRoles::ProgressRole);
        if (data.isValid() && progressData.isValid()) {
            auto name = data.value<QString>();
            auto progress = progressData.value<double>();
            if (progress > 0) {
                auto cancelButtonWidth = 20;
                auto progressBarOption = QStyleOptionProgressBar{};
                auto progressRect = option.rect;
                progressRect.setWidth(progressRect.width() - cancelButtonWidth);
                progressBarOption.rect = progressRect;
                progressBarOption.minimum = 0;
                progressBarOption.maximum = 100;
                progressBarOption.progress = progress;
                progressBarOption.text
                    = QString("%1 %2").arg(name).arg(QString::number(progress, 'f', 2) + "%");
                progressBarOption.textVisible = true;
                progressBarOption.textAlignment = Qt::AlignCenter;


                QApplication::style()->drawControl(QStyle::CE_ProgressBar, &progressBarOption,
                                                   painter);

                // Cancel button
                auto buttonRect = QRect(progressRect.right(), option.rect.top(), cancelButtonWidth,
                                        option.rect.height());
                auto buttonOption = QStyleOptionButton{};
                buttonOption.rect = buttonRect;
                buttonOption.text = "X";

                QApplication::style()->drawControl(QStyle::CE_PushButton, &buttonOption, painter);
            }
            else {
                QStyledItemDelegate::paint(painter, option, index);
            }
        }
        else {
            QStyledItemDelegate::paint(painter, option, index);
        }
    }

    bool editorEvent(QEvent *event, QAbstractItemModel *model, const QStyleOptionViewItem &option,
                     const QModelIndex &index)
    {
        if (event->type() == QEvent::MouseButtonRelease) {
            auto data = index.data(Qt::DisplayRole);
            auto progressData = index.data(VariableRoles::ProgressRole);
            if (data.isValid() && progressData.isValid()) {
                auto cancelButtonWidth = 20;
                auto progressRect = option.rect;
                progressRect.setWidth(progressRect.width() - cancelButtonWidth);
                // Cancel button
                auto buttonRect = QRect(progressRect.right(), option.rect.top(), cancelButtonWidth,
                                        option.rect.height());

                auto e = (QMouseEvent *)event;
                auto clickX = e->x();
                auto clickY = e->y();

                auto x = buttonRect.left();   // the X coordinate
                auto y = buttonRect.top();    // the Y coordinate
                auto w = buttonRect.width();  // button width
                auto h = buttonRect.height(); // button height

                if (clickX > x && clickX < x + w) {
                    if (clickY > y && clickY < y + h) {
                        auto variableModel = sqpApp->variableController().variableModel();
                        variableModel->abortProgress(index);
                    }
                }
                else {
                    QStyledItemDelegate::editorEvent(event, model, option, index);
                }
            }
            else {
                QStyledItemDelegate::editorEvent(event, model, option, index);
            }
        }
        else {
            QStyledItemDelegate::editorEvent(event, model, option, index);
        }
    }
};

VariableInspectorWidget::VariableInspectorWidget(QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VariableInspectorWidget},
          m_ProgressBarItemDelegate{new QProgressBarItemDelegate{this}}
{
    ui->setupUi(this);

    // Sets model for table
    //    auto sortFilterModel = new QSortFilterProxyModel{this};
    //    sortFilterModel->setSourceModel(sqpApp->variableController().variableModel());

    auto variableModel = sqpApp->variableController().variableModel();
    ui->tableView->setModel(variableModel);

    // Adds extra signal/slot between view and model, so the view can be updated instantly when
    // there is a change of data in the model
    connect(variableModel, SIGNAL(dataChanged(const QModelIndex &, const QModelIndex &)), this,
            SLOT(refresh()));

    ui->tableView->setSelectionModel(sqpApp->variableController().variableSelectionModel());
    ui->tableView->setItemDelegateForColumn(0, m_ProgressBarItemDelegate);

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
    auto selectedRows = ui->tableView->selectionModel()->selectedRows();

    // Gets the model to retrieve the underlying selected variables
    auto model = sqpApp->variableController().variableModel();
    auto selectedVariables = QVector<std::shared_ptr<Variable> >{};
    for (const auto &selectedRow : qAsConst(selectedRows)) {
        if (auto selectedVariable = model->variable(selectedRow.row())) {
            selectedVariables.push_back(selectedVariable);
        }
    }

    QMenu tableMenu{};

    // Emits a signal so that potential receivers can populate the menu before displaying it
    emit tableMenuAboutToBeDisplayed(&tableMenu, selectedVariables);

    // Adds menu-specific actions
    if (!selectedVariables.isEmpty()) {
        tableMenu.addSeparator();

        // 'Rename' action (only if one variable selected)
        if (selectedVariables.size() == 1) {
            auto selectedVariable = selectedVariables.front();

            auto renameFun = [&selectedVariable, &model, this]() {
            };

            tableMenu.addAction(tr("Rename..."), renameFun);
        }

        // 'Delete' action
        auto deleteFun = [&selectedVariables]() {
            sqpApp->variableController().deleteVariables(selectedVariables);
        };

        tableMenu.addAction(QIcon{":/icones/delete.png"}, tr("Delete"), deleteFun);
    }

    if (!tableMenu.isEmpty()) {
        // Generates menu header (inserted before first action)
        auto firstAction = tableMenu.actions().first();
        auto headerAction = new QWidgetAction{&tableMenu};
        headerAction->setDefaultWidget(new VariableMenuHeaderWidget{selectedVariables, &tableMenu});
        tableMenu.insertAction(firstAction, headerAction);

        // Displays menu
        tableMenu.exec(QCursor::pos());
    }
}

void VariableInspectorWidget::refresh() noexcept
{
    ui->tableView->viewport()->update();
}
