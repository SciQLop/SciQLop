#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <QMutex>
#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

namespace {

/**
 * Searches in metadata for a value that can be converted to DataSeriesType
 * @param metadata the metadata where to search
 * @return the value converted to a DataSeriesType if it was found, UNKNOWN type otherwise
 * @sa DataSeriesType
 */
DataSeriesType findDataSeriesType(const QVariantHash &metadata)
{
    auto dataSeriesType = DataSeriesType::UNKNOWN;

    // Go through the metadata and stop at the first value that could be converted to DataSeriesType
    for (auto it = metadata.cbegin(), end = metadata.cend();
         it != end && dataSeriesType == DataSeriesType::UNKNOWN; ++it) {
        dataSeriesType = DataSeriesTypeUtils::fromString(it.value().toString());
    }

    return dataSeriesType;
}

} // namespace

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const QVariantHash &metadata)
            : m_Name{name},
              m_Range{INVALID_RANGE},
              m_CacheRange{INVALID_RANGE},
              m_Metadata{metadata},
              m_DataSeries{nullptr},
              m_RealRange{INVALID_RANGE},
              m_NbPoints{0},
              m_Type{findDataSeriesType(m_Metadata)}
    {
    }

    VariablePrivate(const VariablePrivate &other)
            : m_Name{other.m_Name},
              m_Range{other.m_Range},
              m_CacheRange{other.m_CacheRange},
              m_Metadata{other.m_Metadata},
              m_DataSeries{other.m_DataSeries != nullptr ? other.m_DataSeries->clone() : nullptr},
              m_RealRange{other.m_RealRange},
              m_NbPoints{other.m_NbPoints},
              m_Type{findDataSeriesType(m_Metadata)}
    {
    }

    void lockRead() { m_Lock.lockForRead(); }
    void lockWrite() { m_Lock.lockForWrite(); }
    void unlock() { m_Lock.unlock(); }

    void purgeDataSeries()
    {
        if (m_DataSeries) {
            m_DataSeries->purge(m_CacheRange.m_TStart, m_CacheRange.m_TEnd);
        }
        updateRealRange();
        updateNbPoints();
    }

    void updateNbPoints() { m_NbPoints = m_DataSeries ? m_DataSeries->nbPoints() : 0; }

    /// Updates real range according to current variable range and data series
    void updateRealRange()
    {
        if (m_DataSeries) {
            m_DataSeries->lockRead();
            auto end = m_DataSeries->cend();
            auto minXAxisIt = m_DataSeries->minXAxisData(m_Range.m_TStart);
            auto maxXAxisIt = m_DataSeries->maxXAxisData(m_Range.m_TEnd);

            m_RealRange
                = (minXAxisIt != end && maxXAxisIt != end && minXAxisIt->x() <= maxXAxisIt->x())
                      ? DateTimeRange{minXAxisIt->x(), maxXAxisIt->x()}
                      : INVALID_RANGE;
            m_DataSeries->unlock();
        }
        else {
            m_RealRange = INVALID_RANGE;
        }
    }

    QString m_Name;

    DateTimeRange m_Range;
    DateTimeRange m_CacheRange;
    QVariantHash m_Metadata;
    std::shared_ptr<IDataSeries> m_DataSeries;
    DateTimeRange m_RealRange;
    int m_NbPoints;
    DataSeriesType m_Type;

    QReadWriteLock m_Lock;
};

Variable::Variable(const QString &name, const QVariantHash &metadata)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, metadata)}
{
}

Variable::Variable(const Variable &other)
        : impl{spimpl::make_unique_impl<VariablePrivate>(*other.impl)}
{
}

std::shared_ptr<Variable> Variable::clone() const
{
    return std::make_shared<Variable>(*this);
}

QString Variable::name() const noexcept
{
    impl->lockRead();
    auto name = impl->m_Name;
    impl->unlock();
    return name;
}

void Variable::setName(const QString &name) noexcept
{
    impl->lockWrite();
    impl->m_Name = name;
    impl->unlock();
}

DateTimeRange Variable::range() const noexcept
{
    impl->lockRead();
    auto range = impl->m_Range;
    impl->unlock();
    return range;
}

void Variable::setRange(const DateTimeRange &range) noexcept
{
    impl->lockWrite();
    impl->m_Range = range;
    impl->updateRealRange();
    impl->unlock();
}

DateTimeRange Variable::cacheRange() const noexcept
{
    impl->lockRead();
    auto cacheRange = impl->m_CacheRange;
    impl->unlock();
    return cacheRange;
}

void Variable::setCacheRange(const DateTimeRange &cacheRange) noexcept
{
    impl->lockWrite();
    if (cacheRange != impl->m_CacheRange) {
        impl->m_CacheRange = cacheRange;
    }
    impl->unlock();
}

int Variable::nbPoints() const noexcept
{
    return impl->m_NbPoints;
}

DateTimeRange Variable::realRange() const noexcept
{
    return impl->m_RealRange;
}

void Variable::mergeDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCDebug(LOG_Variable()) << "TORM Variable::mergeDataSeries"
                            << QThread::currentThread()->objectName();
    if (!dataSeries) {
        /// @todo ALX : log
        return;
    }

    auto dataInit = false;

    // Add or merge the data
    impl->lockWrite();
    if (!impl->m_DataSeries) {
        impl->m_DataSeries = dataSeries->clone();
        dataInit = true;
    }
    else {
        impl->m_DataSeries->merge(dataSeries.get());
    }
    impl->purgeDataSeries();
    impl->unlock();

    if (dataInit) {
        emit dataInitialized();
    }
}


std::shared_ptr<IDataSeries> Variable::dataSeries() const noexcept
{
    impl->lockRead();
    auto dataSeries = impl->m_DataSeries;
    impl->unlock();

    return dataSeries;
}

DataSeriesType Variable::type() const noexcept
{
    impl->lockRead();
    auto type = impl->m_Type;
    impl->unlock();

    return type;
}

QVariantHash Variable::metadata() const noexcept
{
    impl->lockRead();
    auto metadata = impl->m_Metadata;
    impl->unlock();
    return metadata;
}

bool Variable::contains(const DateTimeRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_Range.contains(range);
    impl->unlock();
    return res;
}

bool Variable::intersect(const DateTimeRange &range) const noexcept
{

    impl->lockRead();
    auto res = impl->m_Range.intersect(range);
    impl->unlock();
    return res;
}

bool Variable::isInside(const DateTimeRange &range) const noexcept
{
    impl->lockRead();
    auto res = range.contains(DateTimeRange{impl->m_Range.m_TStart, impl->m_Range.m_TEnd});
    impl->unlock();
    return res;
}

bool Variable::cacheContains(const DateTimeRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_CacheRange.contains(range);
    impl->unlock();
    return res;
}

bool Variable::cacheIntersect(const DateTimeRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_CacheRange.intersect(range);
    impl->unlock();
    return res;
}

bool Variable::cacheIsInside(const DateTimeRange &range) const noexcept
{
    impl->lockRead();
    auto res = range.contains(DateTimeRange{impl->m_CacheRange.m_TStart, impl->m_CacheRange.m_TEnd});
    impl->unlock();
    return res;
}


QVector<DateTimeRange> Variable::provideNotInCacheRangeList(const DateTimeRange &range) const noexcept
{
    // This code assume that cach in contigue. Can return 0, 1 or 2 SqpRange
    auto notInCache = QVector<DateTimeRange>{};
    if (impl->m_CacheRange != INVALID_RANGE) {

        if (!this->cacheContains(range)) {
            if (range.m_TEnd <= impl->m_CacheRange.m_TStart
                || range.m_TStart >= impl->m_CacheRange.m_TEnd) {
                notInCache << range;
            }
            else if (range.m_TStart < impl->m_CacheRange.m_TStart
                     && range.m_TEnd <= impl->m_CacheRange.m_TEnd) {
                notInCache << DateTimeRange{range.m_TStart, impl->m_CacheRange.m_TStart};
            }
            else if (range.m_TStart < impl->m_CacheRange.m_TStart
                     && range.m_TEnd > impl->m_CacheRange.m_TEnd) {
                notInCache << DateTimeRange{range.m_TStart, impl->m_CacheRange.m_TStart}
                           << DateTimeRange{impl->m_CacheRange.m_TEnd, range.m_TEnd};
            }
            else if (range.m_TStart < impl->m_CacheRange.m_TEnd) {
                notInCache << DateTimeRange{impl->m_CacheRange.m_TEnd, range.m_TEnd};
            }
            else {
                qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                           << QThread::currentThread();
            }
        }
    }
    else {
        notInCache << range;
    }

    return notInCache;
}

QVector<DateTimeRange> Variable::provideInCacheRangeList(const DateTimeRange &range) const noexcept
{
    // This code assume that cach in contigue. Can return 0 or 1 SqpRange

    auto inCache = QVector<DateTimeRange>{};

    if (impl->m_CacheRange != INVALID_RANGE) {

        if (this->cacheIntersect(range)) {
            if (range.m_TStart <= impl->m_CacheRange.m_TStart
                && range.m_TEnd >= impl->m_CacheRange.m_TStart
                && range.m_TEnd < impl->m_CacheRange.m_TEnd) {
                inCache << DateTimeRange{impl->m_CacheRange.m_TStart, range.m_TEnd};
            }

            else if (range.m_TStart >= impl->m_CacheRange.m_TStart
                     && range.m_TEnd <= impl->m_CacheRange.m_TEnd) {
                inCache << range;
            }
            else if (range.m_TStart > impl->m_CacheRange.m_TStart
                     && range.m_TEnd > impl->m_CacheRange.m_TEnd) {
                inCache << DateTimeRange{range.m_TStart, impl->m_CacheRange.m_TEnd};
            }
            else if (range.m_TStart <= impl->m_CacheRange.m_TStart
                     && range.m_TEnd >= impl->m_CacheRange.m_TEnd) {
                inCache << impl->m_CacheRange;
            }
            else {
                qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                           << QThread::currentThread();
            }
        }
    }

    return inCache;
}


QVector<DateTimeRange> Variable::provideNotInCacheRangeList(const DateTimeRange &oldRange,
                                                       const DateTimeRange &nextRange)
{

    // This code assume that cach in contigue. Can return 0, 1 or 2 SqpRange
    auto notInCache = QVector<DateTimeRange>{};
    if (oldRange != INVALID_RANGE) {

        if (!oldRange.contains(nextRange)) {
            if (nextRange.m_TEnd <= oldRange.m_TStart || nextRange.m_TStart >= oldRange.m_TEnd) {
                notInCache << nextRange;
            }
            else if (nextRange.m_TStart < oldRange.m_TStart
                     && nextRange.m_TEnd <= oldRange.m_TEnd) {
                notInCache << DateTimeRange{nextRange.m_TStart, oldRange.m_TStart};
            }
            else if (nextRange.m_TStart < oldRange.m_TStart && nextRange.m_TEnd > oldRange.m_TEnd) {
                notInCache << DateTimeRange{nextRange.m_TStart, oldRange.m_TStart}
                           << DateTimeRange{oldRange.m_TEnd, nextRange.m_TEnd};
            }
            else if (nextRange.m_TStart < oldRange.m_TEnd) {
                notInCache << DateTimeRange{oldRange.m_TEnd, nextRange.m_TEnd};
            }
            else {
                qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                           << QThread::currentThread();
            }
        }
    }
    else {
        notInCache << nextRange;
    }

    return notInCache;
}

QVector<DateTimeRange> Variable::provideInCacheRangeList(const DateTimeRange &oldRange,
                                                    const DateTimeRange &nextRange)
{
    // This code assume that cach is contigue. Can return 0 or 1 SqpRange

    auto inCache = QVector<DateTimeRange>{};

    if (oldRange != INVALID_RANGE) {

        if (oldRange.intersect(nextRange)) {
            if (nextRange.m_TStart <= oldRange.m_TStart && nextRange.m_TEnd >= oldRange.m_TStart
                && nextRange.m_TEnd < oldRange.m_TEnd) {
                inCache << DateTimeRange{oldRange.m_TStart, nextRange.m_TEnd};
            }

            else if (nextRange.m_TStart >= oldRange.m_TStart
                     && nextRange.m_TEnd <= oldRange.m_TEnd) {
                inCache << nextRange;
            }
            else if (nextRange.m_TStart > oldRange.m_TStart && nextRange.m_TEnd > oldRange.m_TEnd) {
                inCache << DateTimeRange{nextRange.m_TStart, oldRange.m_TEnd};
            }
            else if (nextRange.m_TStart <= oldRange.m_TStart
                     && nextRange.m_TEnd >= oldRange.m_TEnd) {
                inCache << oldRange;
            }
            else {
                qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                           << QThread::currentThread();
            }
        }
    }

    return inCache;
}
