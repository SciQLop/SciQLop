#include "Time/TimeController.h"

#include <QDataStream>

Q_LOGGING_CATEGORY(LOG_TimeController, "TimeController")

struct TimeController::TimeControllerPrivate {

    SqpRange m_DateTime;
};

TimeController::TimeController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<TimeControllerPrivate>()}
{
    qCDebug(LOG_TimeController()) << tr("TimeController construction");
}

SqpRange TimeController::dateTime() const noexcept
{
    return impl->m_DateTime;
}

QByteArray TimeController::mimeDataForTimeRange(const SqpRange &timeRange)
{
    QByteArray encodedData;
    QDataStream stream{&encodedData, QIODevice::WriteOnly};

    stream << timeRange.m_TStart << timeRange.m_TEnd;

    return encodedData;
}

SqpRange TimeController::timeRangeForMimeData(const QByteArray &mimeData)
{
    QDataStream stream{mimeData};

    SqpRange timeRange;
    stream >> timeRange.m_TStart >> timeRange.m_TEnd;

    return timeRange;
}

void TimeController::setDateTimeRange(SqpRange dateTime)
{
    impl->m_DateTime = dateTime;
}

void TimeController::onTimeNotify()
{
    emit timeUpdated(impl->m_DateTime);
}
