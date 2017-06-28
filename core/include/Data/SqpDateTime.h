#ifndef SCIQLOP_SQPDATETIME_H
#define SCIQLOP_SQPDATETIME_H

#include <QObject>
/**
 * @brief The SqpDateTime struct holds the information of time parameters
 */
struct SqpDateTime {
    /// Start time
    double m_TStart;
    /// End time
    double m_TEnd;

    bool contains(const SqpDateTime &dateTime)
    {
        return (m_TStart <= dateTime.m_TStart && m_TEnd >= dateTime.m_TEnd);
    }

    bool intersect(const SqpDateTime &dateTime)
    {
        return (m_TEnd >= dateTime.m_TStart && m_TStart <= dateTime.m_TEnd);
    }
};

// Required for using shared_ptr in signals/slots
Q_DECLARE_METATYPE(SqpDateTime)

#endif // SCIQLOP_SQPDATETIME_H
