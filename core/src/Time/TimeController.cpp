#include "Time/TimeController.h"

#include <QDataStream>

Q_LOGGING_CATEGORY(LOG_TimeController, "TimeController")

struct TimeController::TimeControllerPrivate {

    DateTimeRange m_DateTime;
};

TimeController::TimeController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<TimeControllerPrivate>()}
{
    qCDebug(LOG_TimeController()) << tr("TimeController construction");
}

DateTimeRange TimeController::dateTime() const noexcept
{
    return impl->m_DateTime;
}

QByteArray TimeController::mimeDataForTimeRange(const DateTimeRange &timeRange)
{
    QByteArray encodedData;
    QDataStream stream{&encodedData, QIODevice::WriteOnly};

    stream << timeRange.m_TStart << timeRange.m_TEnd;

    return encodedData;
}

DateTimeRange TimeController::timeRangeForMimeData(const QByteArray &mimeData)
{
    QDataStream stream{mimeData};

    DateTimeRange timeRange;
    stream >> timeRange.m_TStart >> timeRange.m_TEnd;

    return timeRange;
}

void TimeController::setDateTimeRange(DateTimeRange dateTime)
{
    impl->m_DateTime = dateTime;
}

void TimeController::onTimeNotify()
{
    emit timeUpdated(impl->m_DateTime);
}
