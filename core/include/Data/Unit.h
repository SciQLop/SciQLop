#ifndef SCIQLOP_UNIT_H
#define SCIQLOP_UNIT_H

#include <Common/MetaTypes.h>

#include <QString>
#include <tuple>

struct Unit {
    explicit Unit(const QString &name = {}, bool timeUnit = false)
            : m_Name{name}, m_TimeUnit{timeUnit}
    {
    }

    inline bool operator==(const Unit &other) const
    {
        return std::tie(m_Name, m_TimeUnit) == std::tie(other.m_Name, other.m_TimeUnit);
    }
    inline bool operator!=(const Unit &other) const { return !(*this == other); }

    QString m_Name;  ///< Unit name
    bool m_TimeUnit; ///< The unit is a unit of time (UTC)
};

SCIQLOP_REGISTER_META_TYPE(UNIT_REGISTRY, Unit)

#endif // SCIQLOP_UNIT_H
