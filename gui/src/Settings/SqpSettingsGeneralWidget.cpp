#include "Settings/SqpSettingsGeneralWidget.h"

#include "ui_SqpSettingsGeneralWidget.h"

SqpSettingsGeneralWidget::SqpSettingsGeneralWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::SqpSettingsGeneralWidget}
{
    ui->setupUi(this);
}

SqpSettingsGeneralWidget::~SqpSettingsGeneralWidget() noexcept
{
    delete ui;
}
