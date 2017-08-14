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
            : m_Name{name}, m_Range{dateTime}, m_Metadata{metadata}, m_DataSeries{nullptr}
    {
    }

    void lockRead() { m_Lock.lockForRead(); }
    void lockWrite() { m_Lock.lockForWrite(); }
    void unlock() { m_Lock.unlock(); }

    QString m_Name;

    SqpRange m_Range;
    SqpRange m_CacheRange;
    QVariantHash m_Metadata;
    std::unique_ptr<IDataSeries> m_DataSeries;

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

void Variable::setDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCInfo(LOG_Variable()) << "Variable::setDataSeries" << QThread::currentThread()->objectName();
    if (!dataSeries) {
        /// @todo ALX : log
        return;
    }
    impl->lockWrite();
    impl->m_DataSeries = dataSeries->clone();
    impl->unlock();
}

void Variable::mergeDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCDebug(LOG_Variable()) << "Variable::mergeDataSeries"
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
    auto subData = this->dataSeries()->subData(this->cacheRange());
    qCCritical(LOG_Variable()) << "TORM: Variable::mergeDataSeries sub" << subData->range();
    this->setDataSeries(subData);
    qCCritical(LOG_Variable()) << "TORM: Variable::mergeDataSeries set"
                               << this->dataSeries()->range();
}

IDataSeries *Variable::dataSeries() const noexcept
{
    impl->lockRead();
    auto dataSeries = impl->m_DataSeries.get();
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
