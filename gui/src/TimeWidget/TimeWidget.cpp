#include "TimeWidget/TimeWidget.h"
#include "ui_TimeWidget.h"

#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>

#include <SqpApplication.h>
#include <Time/TimeController.h>

#include <QDragEnterEvent>
#include <QDropEvent>
#include <QMimeData>

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

    auto dateTime = SqpRange{DateUtils::secondsSinceEpoch(startDateTime),
                             DateUtils::secondsSinceEpoch(endDateTime)};

    sqpApp->timeController().onTimeToUpdate(dateTime);
}


TimeWidget::~TimeWidget()
{
    delete ui;
}

void TimeWidget::setTimeRange(SqpRange time)
{
    auto startDateTime = DateUtils::dateTime(time.m_TStart);
    auto endDateTime = DateUtils::dateTime(time.m_TEnd);

    ui->startDateTimeEdit->setDateTime(startDateTime);
    ui->endDateTimeEdit->setDateTime(endDateTime);
}

void TimeWidget::onTimeUpdateRequested()
{
    auto dateTime = SqpRange{DateUtils::secondsSinceEpoch(ui->startDateTimeEdit->dateTime()),
                             DateUtils::secondsSinceEpoch(ui->endDateTimeEdit->dateTime())};

    emit timeUpdated(std::move(dateTime));
}

void TimeWidget::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasFormat(MIME_TYPE_TIME_RANGE)) {
        event->acceptProposedAction();
        setStyleSheet("QDateTimeEdit{background-color: #BBD5EE; border:2px solid #2A7FD4}");
    }
    else {
        event->ignore();
    }
}

void TimeWidget::dragLeaveEvent(QDragLeaveEvent *event)
{
    setStyleSheet(QString());
}

void TimeWidget::dropEvent(QDropEvent *event)
{
    if (event->mimeData()->hasFormat(MIME_TYPE_TIME_RANGE)) {
        auto mimeData = event->mimeData()->data(MIME_TYPE_TIME_RANGE);
        auto timeRange = TimeController::timeRangeForMimeData(mimeData);

        setTimeRange(timeRange);
    }
    else {
        event->ignore();
    }

    setStyleSheet(QString());
}
