#ifndef SCIQLOP_VARIABLECACHESTRATEGYFACTORY_H
#define SCIQLOP_VARIABLECACHESTRATEGYFACTORY_H


#include <memory>
#include <stdexcept>

#include "VariableCacheStrategy.h"
#include "VariableSingleThresholdCacheStrategy.h"

#include <QLoggingCategory>
#include <QString>

Q_LOGGING_CATEGORY(LOG_VariableCacheStrategyFactory, "VariableCacheStrategyFactory")

enum class CacheStrategy { SingleThreshold, TwoThreashold };

class VariableCacheStrategyFactory {

    using cacheStratPtr = std::unique_ptr<VariableCacheStrategy>;

public:
    static cacheStratPtr createCacheStrategy(CacheStrategy specificStrategy)
    {
        switch (specificStrategy) {
            case CacheStrategy::SingleThreshold: {
                return std::unique_ptr<VariableCacheStrategy>{
                    new VariableSingleThresholdCacheStrategy{}};
                break;
            }
            case CacheStrategy::TwoThreashold: {
                qCCritical(LOG_VariableCacheStrategyFactory())
                    << QObject::tr("cache strategy not implemented yet");
                break;
            }
            default:
                qCCritical(LOG_VariableCacheStrategyFactory())
                    << QObject::tr("Unknown cache strategy");
        }

        return nullptr;
    }
};


#endif // VARIABLECACHESTRATEGYFACTORY_H
