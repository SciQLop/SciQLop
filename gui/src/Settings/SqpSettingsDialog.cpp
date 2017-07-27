#include "Settings/SqpSettingsDialog.h"
#include "ui_SqpSettingsDialog.h"

SqpSettingsDialog::SqpSettingsDialog(QWidget *parent)
        : QDialog{parent}, ui{new Ui::SqpSettingsDialog}
{
    ui->setupUi(this);

    // Connection to change the current page to the selection of an entry in the list
    connect(ui->listWidget, &QListWidget::currentRowChanged, ui->stackedWidget,
            &QStackedWidget::setCurrentIndex);
}

SqpSettingsDialog::~SqpSettingsDialog() noexcept
{
    delete ui;
}
void SqpSettingsDialog::registerWidget(const QString &name, QWidget *widget) noexcept
{
    auto newItem = new QListWidgetItem{ui->listWidget};
    newItem->setText(name);

    ui->stackedWidget->addWidget(widget);

    // Selects widget if it's the first in the dialog
    if (ui->listWidget->count() == 1) {
        ui->listWidget->setCurrentItem(newItem);
    }
}
