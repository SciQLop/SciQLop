#include "Variable/VariableCacheController.h"

#include "Variable/Variable.h"
#include <unordered_map>

struct VariableCacheController::VariableCacheControllerPrivate {

    std::unordered_map<std::shared_ptr<Variable>, QVector<SqpDateTime> >
        m_VariableToSqpDateTimeListMap;

    void addInCacheDataByEnd(const SqpDateTime &dateTime, QVector<SqpDateTime> &dateTimeList,
                             QVector<SqpDateTime> &notInCache, int cacheIndex,
                             double currentTStart);

    void addInCacheDataByStart(const SqpDateTime &dateTime, QVector<SqpDateTime> &dateTimeList,
                               QVector<SqpDateTime> &notInCache, int cacheIndex,
                               double currentTStart);
};


VariableCacheController::VariableCacheController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<VariableCacheControllerPrivate>()}
{
}

void VariableCacheController::addDateTime(std::shared_ptr<Variable> variable,
                                          const SqpDateTime &dateTime)
{
    if (variable) {
        // TODO: squeeze the map to let it only some SqpDateTime without intersection
        impl->m_VariableToSqpDateTimeListMap[variable].push_back(dateTime);
    }
}

QVector<SqpDateTime>
VariableCacheController::provideNotInCacheDateTimeList(std::shared_ptr<Variable> variable,
                                                       const SqpDateTime &dateTime)
{
    auto notInCache = QVector<SqpDateTime>{};

    // This algorithm is recursif. The idea is to localise the start time then the end time in the
    // list of date time request associated to the variable
    // We assume that the list is ordered in a way that l(0) < l(1). We assume also a < b
    // (with a & b of type SqpDateTime) means ts(b) > te(a)

    impl->addInCacheDataByStart(dateTime, impl->m_VariableToSqpDateTimeListMap.at(variable),
                                notInCache, 0, dateTime.m_TStart);

    return notInCache;
}


void VariableCacheController::VariableCacheControllerPrivate::addInCacheDataByEnd(
    const SqpDateTime &dateTime, QVector<SqpDateTime> &dateTimeList,
    QVector<SqpDateTime> &notInCache, int cacheIndex, double currentTStart)
{
    const auto dateTimeListSize = dateTimeList.count();
    if (cacheIndex >= dateTimeListSize) {
        if (currentTStart < dateTime.m_TEnd) {

            // te localised after all other interval: The last interval is [currentTsart, te]
            notInCache.push_back(SqpDateTime{currentTStart, dateTime.m_TEnd});
        }
        return;
    }

    auto currentDateTimeJ = dateTimeList[cacheIndex];
    if (dateTime.m_TEnd <= currentDateTimeJ.m_TStart) {
        // te localised between to interval: The last interval is [currentTsart, te]
        notInCache.push_back(SqpDateTime{currentTStart, dateTime.m_TEnd});
    }
    else {
        notInCache.push_back(SqpDateTime{currentTStart, currentDateTimeJ.m_TStart});
        if (dateTime.m_TEnd > currentDateTimeJ.m_TEnd) {
            // te not localised before the current interval: we need to look at the next interval
            addInCacheDataByEnd(dateTime, dateTimeList, notInCache, ++cacheIndex,
                                currentDateTimeJ.m_TEnd);
        }
    }
}

void VariableCacheController::VariableCacheControllerPrivate::addInCacheDataByStart(
    const SqpDateTime &dateTime, QVector<SqpDateTime> &dateTimeList,
    QVector<SqpDateTime> &notInCache, int cacheIndex, double currentTStart)
{
    const auto dateTimeListSize = dateTimeList.count();
    if (cacheIndex >= dateTimeListSize) {
        // ts localised after all other interval: The last interval is [ts, te]
        notInCache.push_back(SqpDateTime{currentTStart, dateTime.m_TEnd});
        return;
    }

    auto currentDateTimeI = dateTimeList[cacheIndex];
    auto cacheIndexJ = cacheIndex;
    if (currentTStart < currentDateTimeI.m_TStart) {

        // ts localised between to interval: let's localized te
        addInCacheDataByEnd(dateTime, dateTimeList, notInCache, cacheIndexJ, currentTStart);
    }
    else if (dateTime.m_TStart < currentDateTimeI.m_TEnd) {
        // ts not localised before the current interval: we need to look at the next interval
        // We can assume now current tstart is the last interval tend, because data between them are
        // in the cache
        addInCacheDataByStart(dateTime, dateTimeList, notInCache, ++cacheIndex,
                              currentDateTimeI.m_TEnd);
    }
    else {
        // ts not localised before the current interval: we need to look at the next interval
        addInCacheDataByStart(dateTime, dateTimeList, notInCache, ++cacheIndex, currentTStart);
    }
}
