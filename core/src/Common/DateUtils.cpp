#include "Common/DateUtils.h"

QDateTime DateUtils::dateTime(double secs, Qt::TimeSpec timeSpec) noexcept
{
    // Uses msecs to be Qt 4 compatible
    return QDateTime::fromMSecsSinceEpoch(secs * 1000., timeSpec);
}

double DateUtils::secondsSinceEpoch(const QDateTime &dateTime) noexcept
{
    // Uses msecs to be Qt 4 compatible
    return dateTime.toMSecsSinceEpoch() / 1000.;
}
