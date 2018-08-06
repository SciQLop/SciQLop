#include "TimeWidget/TimeWidget.h"
#include "ui_TimeWidget.h"

#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>

#include <DragAndDrop/DragDropGuiController.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>

#include <QDrag>
#include <QDragEnterEvent>
#include <QDropEvent>
#include <QMimeData>


struct TimeWidget::TimeWidgetPrivate {

    explicit TimeWidgetPrivate() {}

    QPoint m_DragStartPosition;
};

TimeWidget::TimeWidget(QWidget *parent)
        : QWidget{parent},
          ui{new Ui::TimeWidget},
          impl{spimpl::make_unique_impl<TimeWidgetPrivate>()}
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

    auto dateTime = DateTimeRange{DateUtils::secondsSinceEpoch(startDateTime),
                             DateUtils::secondsSinceEpoch(endDateTime)};

    sqpApp->timeController().setDateTimeRange(dateTime);
}


TimeWidget::~TimeWidget()
{
    delete ui;
}

void TimeWidget::setTimeRange(DateTimeRange time)
{
    auto startDateTime = DateUtils::dateTime(time.m_TStart);
    auto endDateTime = DateUtils::dateTime(time.m_TEnd);

    ui->startDateTimeEdit->setDateTime(startDateTime);
    ui->endDateTimeEdit->setDateTime(endDateTime);
}

DateTimeRange TimeWidget::timeRange() const
{
    return DateTimeRange{DateUtils::secondsSinceEpoch(ui->startDateTimeEdit->dateTime()),
                    DateUtils::secondsSinceEpoch(ui->endDateTimeEdit->dateTime())};
}

void TimeWidget::onTimeUpdateRequested()
{
    auto dateTime = timeRange();
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
    setStyleSheet(QString{});
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

    setStyleSheet(QString{});
}


void TimeWidget::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        impl->m_DragStartPosition = event->pos();
    }

    QWidget::mousePressEvent(event);
}

void TimeWidget::mouseMoveEvent(QMouseEvent *event)
{
    if (!(event->buttons() & Qt::LeftButton)) {
        return;
    }

    if ((event->pos() - impl->m_DragStartPosition).manhattanLength()
        < QApplication::startDragDistance()) {
        return;
    }

    // Note: The management of the drag object is done by Qt
    auto drag = new QDrag{this};

    auto mimeData = new QMimeData;
    auto timeData = TimeController::mimeDataForTimeRange(timeRange());
    mimeData->setData(MIME_TYPE_TIME_RANGE, timeData);

    drag->setMimeData(mimeData);

    auto pixmap = QPixmap{":/icones/time.png"};
    drag->setPixmap(pixmap.scaledToWidth(22));

    sqpApp->dragDropGuiController().resetDragAndDrop();

    // Note: The exec() is blocking on windows but not on linux and macOS
    drag->exec(Qt::MoveAction | Qt::CopyAction);

    QWidget::mouseMoveEvent(event);
}
