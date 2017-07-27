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
