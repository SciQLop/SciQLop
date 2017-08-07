#include "Time/TimeController.h"

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

void TimeController::onTimeToUpdate(SqpRange dateTime)
{
    impl->m_DateTime = dateTime;
}

void TimeController::onTimeNotify()
{
    emit timeUpdated(impl->m_DateTime);
}
