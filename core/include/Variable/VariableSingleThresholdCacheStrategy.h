#ifndef SCIQLOP_VARIABLESINGLETHRESHOLDCACHESTRATEGY_H
#define SCIQLOP_VARIABLESINGLETHRESHOLDCACHESTRATEGY_H

#include "Settings/SqpSettingsDefs.h"
#include "VariableCacheStrategy.h"


/// This class aims to hande the cache strategy.
class SCIQLOP_CORE_EXPORT VariableSingleThresholdCacheStrategy : public VariableCacheStrategy {
public:
    VariableSingleThresholdCacheStrategy() = default;

    std::pair<SqpRange, SqpRange> computeRange(const SqpRange &vRange,
                                               const SqpRange &rangeRequested) override
    {

        auto varRanges = std::pair<SqpRange, SqpRange>{};

        auto toleranceFactor = SqpSettings::toleranceValue(
            GENERAL_TOLERANCE_AT_UPDATE_KEY, GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE);
        auto tolerance = toleranceFactor * (rangeRequested.m_TEnd - rangeRequested.m_TStart);

        varRanges.first = rangeRequested;
        varRanges.second
            = SqpRange{rangeRequested.m_TStart - tolerance, rangeRequested.m_TEnd + tolerance};

        return varRanges;
    }
};


#endif // SCIQLOP_VARIABLESINGLETHRESHOLDCACHESTRATEGY_H
