#include "Variable/VariableCacheController.h"

#include "Variable/Variable.h"
#include <unordered_map>

#include <QThread>
Q_LOGGING_CATEGORY(LOG_VariableCacheController, "VariableCacheController")

struct VariableCacheController::VariableCacheControllerPrivate {

    std::unordered_map<std::shared_ptr<Variable>, QVector<DateTimeRange> > m_VariableToSqpRangeListMap;

    void addInCacheDataByEnd(const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList,
                             QVector<DateTimeRange> &notInCache, int cacheIndex, double currentTStart);

    void addInCacheDataByStart(const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList,
                               QVector<DateTimeRange> &notInCache, int cacheIndex, double currentTStart);


    void addDateTimeRecurse(const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList,
                            int cacheIndex);
};


VariableCacheController::VariableCacheController(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableCacheControllerPrivate>()}
{
}

void VariableCacheController::addDateTime(std::shared_ptr<Variable> variable,
                                          const DateTimeRange &dateTime)
{
    qCDebug(LOG_VariableCacheController()) << "VariableCacheController::addDateTime"
                                           << QThread::currentThread()->objectName();
    if (variable) {
        auto findVariableIte = impl->m_VariableToSqpRangeListMap.find(variable);
        if (findVariableIte == impl->m_VariableToSqpRangeListMap.end()) {
            impl->m_VariableToSqpRangeListMap[variable].push_back(dateTime);
        }
        else {

            // addDateTime modify the list<SqpRange> of the variable in a way to ensure
            // that the list is ordered : l(0) < l(1). We assume also a < b
            // (with a & b of type SqpRange) means ts(b) > te(a)

            // The algorithm will try the merge of two interval:
            // - dateTime will be compare with the first interval of the list:
            //   A: if it is inferior, it will be inserted and it's finished.
            //   B: if it is in intersection, it will be merge then the merged one
            //      will be compared to the next interval. The old one is remove from the list
            //   C: if it is superior, we do the same with the next interval of the list

            try {
                impl->addDateTimeRecurse(dateTime, impl->m_VariableToSqpRangeListMap.at(variable),
                                         0);
            }
            catch (const std::out_of_range &e) {
                qCWarning(LOG_VariableCacheController()) << "addDateTime" << e.what();
            }
        }
    }
}

void VariableCacheController::clear(std::shared_ptr<Variable> variable) noexcept
{
    if (!variable) {
        qCCritical(LOG_VariableCacheController()) << "Can't clear variable cache: variable is null";
        return;
    }

    auto nbEntries = impl->m_VariableToSqpRangeListMap.erase(variable);

    auto clearCacheMessage
        = (nbEntries != 0)
              ? tr("Variable cache cleared for variable %1").arg(variable->name())
              : tr("No deletion of variable cache: no cache was associated with the variable");
    qCDebug(LOG_VariableCacheController()) << clearCacheMessage;
}

QVector<DateTimeRange>
VariableCacheController::provideNotInCacheDateTimeList(std::shared_ptr<Variable> variable,
                                                       const DateTimeRange &dateTime)
{
    qCDebug(LOG_VariableCacheController())
        << "VariableCacheController::provideNotInCacheDateTimeList"
        << QThread::currentThread()->objectName();
    auto notInCache = QVector<DateTimeRange>{};

    // This algorithm is recursif. The idea is to localise the start time then the end time in the
    // list of date time request associated to the variable
    // We assume that the list is ordered in a way that l(0) < l(1). We assume also a < b
    // (with a & b of type SqpRange) means ts(b) > te(a)
    auto it = impl->m_VariableToSqpRangeListMap.find(variable);
    if (it != impl->m_VariableToSqpRangeListMap.end()) {
        impl->addInCacheDataByStart(dateTime, it->second, notInCache, 0, dateTime.m_TStart);
    }
    else {
        notInCache << dateTime;
    }

    return notInCache;
}

QVector<DateTimeRange>
VariableCacheController::dateCacheList(std::shared_ptr<Variable> variable) const noexcept
{
    qCDebug(LOG_VariableCacheController()) << "VariableCacheController::dateCacheList"
                                           << QThread::currentThread()->objectName();
    try {
        return impl->m_VariableToSqpRangeListMap.at(variable);
    }
    catch (const std::out_of_range &e) {
        qCWarning(LOG_VariableCacheController()) << e.what();
        return QVector<DateTimeRange>{};
    }
}

void VariableCacheController::VariableCacheControllerPrivate::addDateTimeRecurse(
    const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList, int cacheIndex)
{
    const auto dateTimeListSize = dateTimeList.count();
    if (cacheIndex >= dateTimeListSize) {
        dateTimeList.push_back(dateTime);
        // there is no anymore interval to compore, we can just push_back it
        return;
    }

    auto currentDateTime = dateTimeList[cacheIndex];

    if (dateTime.m_TEnd < currentDateTime.m_TStart) {
        // The compared one is < to current one compared, we can insert it
        dateTimeList.insert(cacheIndex, dateTime);
    }
    else if (dateTime.m_TStart > currentDateTime.m_TEnd) {
        // The compared one is > to current one compared  we can comparet if to the next one
        addDateTimeRecurse(dateTime, dateTimeList, ++cacheIndex);
    }
    else {
        // Merge cases: we need to merge the two interval, remove the old one from the list then
        // rerun the algo from this index with the merged interval
        auto mTStart = std::min(dateTime.m_TStart, currentDateTime.m_TStart);
        auto mTEnd = std::max(dateTime.m_TEnd, currentDateTime.m_TEnd);
        auto mergeDateTime = DateTimeRange{mTStart, mTEnd};

        dateTimeList.remove(cacheIndex);
        addDateTimeRecurse(mergeDateTime, dateTimeList, cacheIndex);
    }
}


void VariableCacheController::VariableCacheControllerPrivate::addInCacheDataByEnd(
    const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList, QVector<DateTimeRange> &notInCache,
    int cacheIndex, double currentTStart)
{
    const auto dateTimeListSize = dateTimeList.count();
    if (cacheIndex >= dateTimeListSize) {
        if (currentTStart < dateTime.m_TEnd) {

            // te localised after all other interval: The last interval is [currentTsart, te]
            notInCache.push_back(DateTimeRange{currentTStart, dateTime.m_TEnd});
        }
        return;
    }

    auto currentDateTimeJ = dateTimeList[cacheIndex];
    if (dateTime.m_TEnd <= currentDateTimeJ.m_TStart) {
        // te localised between to interval: The last interval is [currentTsart, te]
        notInCache.push_back(DateTimeRange{currentTStart, dateTime.m_TEnd});
    }
    else {
        notInCache.push_back(DateTimeRange{currentTStart, currentDateTimeJ.m_TStart});
        if (dateTime.m_TEnd > currentDateTimeJ.m_TEnd) {
            // te not localised before the current interval: we need to look at the next interval
            addInCacheDataByEnd(dateTime, dateTimeList, notInCache, ++cacheIndex,
                                currentDateTimeJ.m_TEnd);
        }
    }
}

void VariableCacheController::VariableCacheControllerPrivate::addInCacheDataByStart(
    const DateTimeRange &dateTime, QVector<DateTimeRange> &dateTimeList, QVector<DateTimeRange> &notInCache,
    int cacheIndex, double currentTStart)
{
    const auto dateTimeListSize = dateTimeList.count();
    if (cacheIndex >= dateTimeListSize) {
        // ts localised after all other interval: The last interval is [ts, te]
        notInCache.push_back(DateTimeRange{currentTStart, dateTime.m_TEnd});
        return;
    }

    auto currentDateTimeI = dateTimeList[cacheIndex];
    if (currentTStart < currentDateTimeI.m_TStart) {

        // ts localised between to interval: let's localized te
        addInCacheDataByEnd(dateTime, dateTimeList, notInCache, cacheIndex, currentTStart);
    }
    else if (currentTStart < currentDateTimeI.m_TEnd) {
        if (dateTime.m_TEnd > currentDateTimeI.m_TEnd) {
            // ts not localised before the current interval: we need to look at the next interval
            // We can assume now current tstart is the last interval tend, because data between them
            // are
            // in the cache
            addInCacheDataByStart(dateTime, dateTimeList, notInCache, ++cacheIndex,
                                  currentDateTimeI.m_TEnd);
        }
    }
    else {
        // ts not localised before the current interval: we need to look at the next interval
        addInCacheDataByStart(dateTime, dateTimeList, notInCache, ++cacheIndex, currentTStart);
    }
}


void VariableCacheController::displayCache(std::shared_ptr<Variable> variable) const
{
    auto variableDateTimeList = impl->m_VariableToSqpRangeListMap.find(variable);
    if (variableDateTimeList != impl->m_VariableToSqpRangeListMap.end()) {
        qCInfo(LOG_VariableCacheController()) << tr("VariableCacheController::displayCache")
                                              << variableDateTimeList->second;
    }
    else {
        qCWarning(LOG_VariableCacheController())
            << tr("Cannot display a variable that is not in the cache");
    }
}
