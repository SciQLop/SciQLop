#ifndef SCIQLOP_SQPRANGE_H
#define SCIQLOP_SQPRANGE_H

#include <QObject>

#include <QDebug>

#include <Common/DateUtils.h>
#include <Common/MetaTypes.h>

#include <cmath>

/**
 * @brief The SqpRange struct holds the information of time parameters
 */
struct DateTimeRange {
    /// Creates SqpRange from dates and times
    static DateTimeRange fromDateTime(const QDate &startDate, const QTime &startTime,
                                 const QDate &endDate, const QTime &endTime)
    {
        return {DateUtils::secondsSinceEpoch(QDateTime{startDate, startTime, Qt::UTC}),
                DateUtils::secondsSinceEpoch(QDateTime{endDate, endTime, Qt::UTC})};
    }

    /// Start time (UTC)
    double m_TStart;
    /// End time (UTC)
    double m_TEnd;

    double delta()const {return this->m_TEnd - this->m_TStart;}

    bool contains(const DateTimeRange &dateTime) const noexcept
    {
        return (m_TStart <= dateTime.m_TStart && m_TEnd >= dateTime.m_TEnd);
    }

    bool intersect(const DateTimeRange &dateTime) const noexcept
    {
        return (m_TEnd >= dateTime.m_TStart && m_TStart <= dateTime.m_TEnd);
    }

    bool operator==(const DateTimeRange &other) const
    {
        auto equals = [](const auto &v1, const auto &v2) {
            return (std::isnan(v1) && std::isnan(v2)) || v1 == v2;
        };

        return equals(m_TStart, other.m_TStart) && equals(m_TEnd, other.m_TEnd);
    }
    bool operator!=(const DateTimeRange &other) const { return !(*this == other); }
};

const auto INVALID_RANGE
    = DateTimeRange{std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN()};

inline QDebug operator<<(QDebug d, DateTimeRange obj)
{
    auto tendDateTimeStart = DateUtils::dateTime(obj.m_TStart);
    auto tendDateTimeEnd = DateUtils::dateTime(obj.m_TEnd);

    d << "ts: " << tendDateTimeStart << " te: " << tendDateTimeEnd;
    return d;
}

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(SQPRANGE_REGISTRY, DateTimeRange)

#endif // SCIQLOP_SQPRANGE_H
