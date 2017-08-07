#include "Variable/VariableCacheStrategy.h"

#include "Settings/SqpSettingsDefs.h"

#include "Variable/Variable.h"
#include "Variable/VariableController.h"

Q_LOGGING_CATEGORY(LOG_VariableCacheStrategy, "VariableCacheStrategy")

struct VariableCacheStrategy::VariableCacheStrategyPrivate {
    VariableCacheStrategyPrivate() : m_CacheStrategy{CacheStrategy::FixedTolerance} {}

    CacheStrategy m_CacheStrategy;
};


VariableCacheStrategy::VariableCacheStrategy(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableCacheStrategyPrivate>()}
{
}

std::pair<SqpRange, SqpRange>
VariableCacheStrategy::computeCacheRange(const SqpRange &vRange, const SqpRange &rangeRequested)
{

    auto varRanges = std::pair<SqpRange, SqpRange>{};

    auto toleranceFactor = SqpSettings::toleranceValue(GENERAL_TOLERANCE_AT_UPDATE_KEY,
                                                       GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE);
    auto tolerance = toleranceFactor * (rangeRequested.m_TEnd - rangeRequested.m_TStart);

    switch (impl->m_CacheStrategy) {
        case CacheStrategy::FixedTolerance: {
            varRanges.first = rangeRequested;
            varRanges.second
                = SqpRange{rangeRequested.m_TStart - tolerance, rangeRequested.m_TEnd + tolerance};
            break;
        }

        case CacheStrategy::TwoThreashold: {
            // TODO Implement
            break;
        }
        default:
            qCCritical(LOG_VariableCacheStrategy())
                << tr("Impossible to use compute the cache range with an unknow cache strategy");
            // No action
            break;
    }

    return varRanges;
}
