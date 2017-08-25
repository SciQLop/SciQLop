#ifndef SCIQLOP_SQPRANGE_H
#define SCIQLOP_SQPRANGE_H

#include <QObject>

#include <QDebug>

#include <Common/DateUtils.h>
#include <Common/MetaTypes.h>

/**
 * @brief The SqpRange struct holds the information of time parameters
 */
struct SqpRange {
    /// Start time (UTC)
    double m_TStart;
    /// End time (UTC)
    double m_TEnd;

    bool contains(const SqpRange &dateTime) const noexcept
    {
        return (m_TStart <= dateTime.m_TStart && m_TEnd >= dateTime.m_TEnd);
    }

    bool intersect(const SqpRange &dateTime) const noexcept
    {
        return (m_TEnd >= dateTime.m_TStart && m_TStart <= dateTime.m_TEnd);
    }

    bool operator==(const SqpRange &other) const
    {
        auto equals = [](const auto &v1, const auto &v2) {
            return (std::isnan(v1) && std::isnan(v2)) || v1 == v2;
        };

        return equals(m_TStart, other.m_TStart) && equals(m_TEnd, other.m_TEnd);
    }
    bool operator!=(const SqpRange &other) const { return !(*this == other); }
};

const auto INVALID_RANGE
    = SqpRange{std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN()};

inline QDebug operator<<(QDebug d, SqpRange obj)
{
    auto tendDateTimeStart = DateUtils::dateTime(obj.m_TStart);
    auto tendDateTimeEnd = DateUtils::dateTime(obj.m_TEnd);

    d << "ts: " << tendDateTimeStart << " te: " << tendDateTimeEnd;
    return d;
}

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(SQPRANGE_REGISTRY, SqpRange)

#endif // SCIQLOP_SQPRANGE_H
