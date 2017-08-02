#include "TimeWidget/TimeWidget.h"
#include "ui_TimeWidget.h"

#include <Common/DateUtils.h>
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

    // Initialisation
    auto endDateTime = QDateTime::currentDateTimeUtc();
    auto startDateTime = endDateTime.addSecs(-3600); // one hour before

    ui->startDateTimeEdit->setDateTime(startDateTime);
    ui->endDateTimeEdit->setDateTime(endDateTime);

    auto dateTime = SqpDateTime{DateUtils::secondsSinceEpoch(startDateTime),
                                DateUtils::secondsSinceEpoch(endDateTime)};

    sqpApp->timeController().onTimeToUpdate(dateTime);
}


TimeWidget::~TimeWidget()
{
    delete ui;
}

void TimeWidget::onTimeUpdateRequested()
{
    auto dateTime = SqpDateTime{DateUtils::secondsSinceEpoch(ui->startDateTimeEdit->dateTime()),
                                DateUtils::secondsSinceEpoch(ui->endDateTimeEdit->dateTime())};

    emit timeUpdated(std::move(dateTime));
}
