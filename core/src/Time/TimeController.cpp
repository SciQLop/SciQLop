#include "Time/TimeController.h"

Q_LOGGING_CATEGORY(LOG_TimeController, "TimeController")

struct TimeController::TimeControllerPrivate {

    SqpDateTime m_DateTime;
};

TimeController::TimeController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<TimeControllerPrivate>()}
{
    qCDebug(LOG_TimeController()) << tr("TimeController construction");
}

SqpDateTime TimeController::dateTime() const noexcept
{
    return impl->m_DateTime;
}

void TimeController::onTimeToUpdate(SqpDateTime dateTime)
{
    impl->m_DateTime = dateTime;

    emit timeUpdated(dateTime);
}
