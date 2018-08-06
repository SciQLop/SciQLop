#ifndef SCIQLOP_VARIABLECACHESTRATEGY_H
#define SCIQLOP_VARIABLECACHESTRATEGY_H

#include "CoreGlobal.h"

#include <QLoggingCategory>
#include <QObject>

#include <Data/SqpRange.h>

#include <QLoggingCategory>

#include <Common/spimpl.h>
#include <utility>


Q_DECLARE_LOGGING_CATEGORY(LOG_VariableCacheStrategy)

class Variable;

/// This class aims to hande the cache strategy.
class SCIQLOP_CORE_EXPORT VariableCacheStrategy {

public:
    virtual ~VariableCacheStrategy() noexcept = default;
    virtual std::pair<DateTimeRange, DateTimeRange> computeRange(const DateTimeRange &vRange,
                                                       const DateTimeRange &rangeRequested)
        = 0;
};


#endif // SCIQLOP_VARIABLECACHESTRATEGY_H
