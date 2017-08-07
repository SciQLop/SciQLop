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

/**
 * Possible types of zoom operation
 */
enum class CacheStrategy { FixedTolerance, TwoThreashold };

/// This class aims to hande the cache strategy.
class SCIQLOP_CORE_EXPORT VariableCacheStrategy : public QObject {
    Q_OBJECT
public:
    explicit VariableCacheStrategy(QObject *parent = 0);

    std::pair<SqpRange, SqpRange> computeCacheRange(const SqpRange &vRange,
                                                    const SqpRange &rangeRequested);

private:
    class VariableCacheStrategyPrivate;
    spimpl::unique_impl_ptr<VariableCacheStrategyPrivate> impl;
};

#endif // SCIQLOP_VARIABLECACHESTRATEGY_H
