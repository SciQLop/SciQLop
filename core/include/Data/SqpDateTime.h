#ifndef SCIQLOP_SQPDATETIME_H
#define SCIQLOP_SQPDATETIME_H

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
};

#endif // SCIQLOP_SQPDATETIME_H
