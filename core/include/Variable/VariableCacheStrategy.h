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
    virtual std::pair<SqpRange, SqpRange> computeRange(const SqpRange &vRange,
                                                       const SqpRange &rangeRequested)
        = 0;
};


#endif // SCIQLOP_VARIABLECACHESTRATEGY_H
