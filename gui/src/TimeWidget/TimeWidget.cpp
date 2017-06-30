#include "TimeWidget/TimeWidget.h"
#include "ui_TimeWidget.h"

#include <SqpApplication.h>
#include <Time/TimeController.h>

TimeWidget::TimeWidget(QWidget *parent) : QWidget{parent}, ui{new Ui::TimeWidget}
{
    ui->setupUi(this);

    ui->applyToolButton->setIcon(sqpApp->style()->standardIcon(QStyle::SP_DialogApplyButton));

    // Connection
    connect(ui->startDateTimeEdit, &QDateTimeEdit::dateTimeChanged, this,
            &TimeWidget::onTimeUpdateRequested);

    connect(ui->endDateTimeEdit, &QDateTimeEdit::dateTimeChanged, this,
            &TimeWidget::onTimeUpdateRequested);


    connect(ui->applyToolButton, &QToolButton::clicked, &sqpApp->timeController(),
            &TimeController::onTimeNotify);
}


TimeWidget::~TimeWidget()
{
    delete ui;
}

void TimeWidget::onTimeUpdateRequested()
{
    auto dateTime = SqpDateTime{
        static_cast<double>(ui->startDateTimeEdit->dateTime().toMSecsSinceEpoch() / 1000.),
        static_cast<double>(ui->endDateTimeEdit->dateTime().toMSecsSinceEpoch()) / 1000.};

    emit timeUpdated(std::move(dateTime));
}
