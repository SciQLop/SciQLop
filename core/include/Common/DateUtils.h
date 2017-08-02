#ifndef SCIQLOP_DATEUTILS_H
#define SCIQLOP_DATEUTILS_H

#include "CoreGlobal.h"

#include <QDateTime>

/**
 * Utility class with methods for dates
 */
struct SCIQLOP_CORE_EXPORT DateUtils {
    /// Converts seconds (since epoch) to datetime. By default, the datetime is in UTC
    static QDateTime dateTime(double secs, Qt::TimeSpec timeSpec = Qt::UTC) noexcept;

    /// Converts datetime to seconds since epoch
    static double secondsSinceEpoch(const QDateTime &dateTime) noexcept;
};

#endif // SCIQLOP_DATEUTILS_H
