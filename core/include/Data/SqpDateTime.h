#ifndef SCIQLOP_SQPDATETIME_H
#define SCIQLOP_SQPDATETIME_H

#include <QObject>

#include <QDateTime>
#include <QDebug>

#include <Common/MetaTypes.h>

/**
 * @brief The SqpDateTime struct holds the information of time parameters
 */
struct SqpDateTime {
    /// Start time
    double m_TStart;
    /// End time
    double m_TEnd;

    bool contains(const SqpDateTime &dateTime) const noexcept
    {
        return (m_TStart <= dateTime.m_TStart && m_TEnd >= dateTime.m_TEnd);
    }

    bool intersect(const SqpDateTime &dateTime) const noexcept
    {
        return (m_TEnd >= dateTime.m_TStart && m_TStart <= dateTime.m_TEnd);
    }
};

inline QDebug operator<<(QDebug d, SqpDateTime obj)
{
    auto tendDateTimeStart = QDateTime::fromMSecsSinceEpoch(obj.m_TStart * 1000);
    auto tendDateTimeEnd = QDateTime::fromMSecsSinceEpoch(obj.m_TEnd * 1000);

    //        QDebug << "ts: " << tendDateTimeStart << " te: " << tendDateTimeEnd;
    d << "ts: " << tendDateTimeStart << " te: " << tendDateTimeEnd;
    return d;
}

// Required for using shared_ptr in signals/slots
SCIQLOP_REGISTER_META_TYPE(SQPDATETIME_REGISTRY, SqpDateTime)

#endif // SCIQLOP_SQPDATETIME_H
