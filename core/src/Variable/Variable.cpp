#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <QMutex>
#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const SqpRange &dateTime,
                             const QVariantHash &metadata)
            : m_Name{name},
              m_Range{dateTime},
              m_Metadata{metadata},
              m_DataSeries{nullptr},
              m_RealRange{INVALID_RANGE}
    {
    }

    void lockRead() { m_Lock.lockForRead(); }
    void lockWrite() { m_Lock.lockForWrite(); }
    void unlock() { m_Lock.unlock(); }

    /// Updates real range according to current variable range and data series
    void updateRealRange()
    {
        if (m_DataSeries) {
            m_DataSeries->lockRead();
            auto end = m_DataSeries->cend();
            auto minXAxisIt = m_DataSeries->minXAxisData(m_Range.m_TStart);
            auto maxXAxisIt = m_DataSeries->maxXAxisData(m_Range.m_TEnd);

            m_RealRange = (minXAxisIt != end && maxXAxisIt != end)
                              ? SqpRange{minXAxisIt->x(), maxXAxisIt->x()}
                              : INVALID_RANGE;
            m_DataSeries->unlock();
        }
        else {
            m_RealRange = INVALID_RANGE;
        }
    }

    QString m_Name;

    SqpRange m_Range;
    SqpRange m_CacheRange;
    QVariantHash m_Metadata;
    std::shared_ptr<IDataSeries> m_DataSeries;
    SqpRange m_RealRange;

    QReadWriteLock m_Lock;
};

Variable::Variable(const QString &name, const SqpRange &dateTime, const QVariantHash &metadata)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, dateTime, metadata)}
{
}

QString Variable::name() const noexcept
{
    impl->lockRead();
    auto name = impl->m_Name;
    impl->unlock();
    return name;
}

SqpRange Variable::range() const noexcept
{
    impl->lockRead();
    auto range = impl->m_Range;
    impl->unlock();
    return range;
}

void Variable::setRange(const SqpRange &range) noexcept
{
    impl->lockWrite();
    impl->m_Range = range;
    impl->updateRealRange();
    impl->unlock();
}

SqpRange Variable::cacheRange() const noexcept
{
    impl->lockRead();
    auto cacheRange = impl->m_CacheRange;
    impl->unlock();
    return cacheRange;
}

void Variable::setCacheRange(const SqpRange &cacheRange) noexcept
{
    impl->lockWrite();
    impl->m_CacheRange = cacheRange;
    impl->unlock();
}

SqpRange Variable::realRange() const noexcept
{
    return impl->m_RealRange;
}

void Variable::setDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCDebug(LOG_Variable()) << "TORM Variable::setDataSeries"
                            << QThread::currentThread()->objectName();
    if (!dataSeries) {
        /// @todo ALX : log
        return;
    }
    impl->lockWrite();
    impl->m_DataSeries = dataSeries->clone();
    impl->updateRealRange();
    impl->unlock();
}

void Variable::mergeDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCDebug(LOG_Variable()) << "TORM Variable::mergeDataSeries"
                            << QThread::currentThread()->objectName();
    if (!dataSeries) {
        /// @todo ALX : log
        return;
    }

    // Add or merge the data
    // Inits the data series of the variable
    impl->lockWrite();
    if (!impl->m_DataSeries) {
        impl->m_DataSeries = dataSeries->clone();
    }
    else {
        impl->m_DataSeries->merge(dataSeries.get());
    }
    impl->unlock();

    // sub the data
    auto subData = this->dataSeries()->subDataSeries(this->cacheRange());
    qCDebug(LOG_Variable()) << "TORM: Variable::mergeDataSeries sub" << subData->range();
    this->setDataSeries(subData);
    qCDebug(LOG_Variable()) << "TORM: Variable::mergeDataSeries set" << this->dataSeries()->range();
}

std::shared_ptr<IDataSeries> Variable::dataSeries() const noexcept
{
    impl->lockRead();
    auto dataSeries = impl->m_DataSeries;
    impl->unlock();

    return dataSeries;
}

QVariantHash Variable::metadata() const noexcept
{
    impl->lockRead();
    auto metadata = impl->m_Metadata;
    impl->unlock();
    return metadata;
}

bool Variable::contains(const SqpRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_Range.contains(range);
    impl->unlock();
    return res;
}

bool Variable::intersect(const SqpRange &range) const noexcept
{

    impl->lockRead();
    auto res = impl->m_Range.intersect(range);
    impl->unlock();
    return res;
}

bool Variable::isInside(const SqpRange &range) const noexcept
{
    impl->lockRead();
    auto res = range.contains(SqpRange{impl->m_Range.m_TStart, impl->m_Range.m_TEnd});
    impl->unlock();
    return res;
}

bool Variable::cacheContains(const SqpRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_CacheRange.contains(range);
    impl->unlock();
    return res;
}

bool Variable::cacheIntersect(const SqpRange &range) const noexcept
{
    impl->lockRead();
    auto res = impl->m_CacheRange.intersect(range);
    impl->unlock();
    return res;
}

bool Variable::cacheIsInside(const SqpRange &range) const noexcept
{
    impl->lockRead();
    auto res = range.contains(SqpRange{impl->m_CacheRange.m_TStart, impl->m_CacheRange.m_TEnd});
    impl->unlock();
    return res;
}


QVector<SqpRange> Variable::provideNotInCacheRangeList(const SqpRange &range) const noexcept
{
    // This code assume that cach in contigue. Can return 0, 1 or 2 SqpRange

    auto notInCache = QVector<SqpRange>{};

    if (!this->cacheContains(range)) {
        if (range.m_TEnd <= impl->m_CacheRange.m_TStart
            || range.m_TStart >= impl->m_CacheRange.m_TEnd) {
            notInCache << range;
        }
        else if (range.m_TStart < impl->m_CacheRange.m_TStart
                 && range.m_TEnd <= impl->m_CacheRange.m_TEnd) {
            notInCache << SqpRange{range.m_TStart, impl->m_CacheRange.m_TStart};
        }
        else if (range.m_TStart < impl->m_CacheRange.m_TStart
                 && range.m_TEnd > impl->m_CacheRange.m_TEnd) {
            notInCache << SqpRange{range.m_TStart, impl->m_CacheRange.m_TStart}
                       << SqpRange{impl->m_CacheRange.m_TEnd, range.m_TEnd};
        }
        else if (range.m_TStart < impl->m_CacheRange.m_TEnd) {
            notInCache << SqpRange{impl->m_CacheRange.m_TEnd, range.m_TEnd};
        }
        else {
            qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                       << QThread::currentThread();
        }
    }

    return notInCache;
}

QVector<SqpRange> Variable::provideInCacheRangeList(const SqpRange &range) const noexcept
{
    // This code assume that cach in contigue. Can return 0 or 1 SqpRange

    auto inCache = QVector<SqpRange>{};


    if (this->intersect(range)) {
        if (range.m_TStart <= impl->m_CacheRange.m_TStart
            && range.m_TEnd >= impl->m_CacheRange.m_TStart
            && range.m_TEnd < impl->m_CacheRange.m_TEnd) {
            inCache << SqpRange{impl->m_CacheRange.m_TStart, range.m_TEnd};
        }

        else if (range.m_TStart >= impl->m_CacheRange.m_TStart
                 && range.m_TEnd <= impl->m_CacheRange.m_TEnd) {
            inCache << range;
        }
        else if (range.m_TStart > impl->m_CacheRange.m_TStart
                 && range.m_TEnd > impl->m_CacheRange.m_TEnd) {
            inCache << SqpRange{range.m_TStart, impl->m_CacheRange.m_TEnd};
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

    return inCache;
}
