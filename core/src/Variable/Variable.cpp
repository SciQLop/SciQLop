#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const SqpRange &dateTime,
                             const QVariantHash &metadata)
            : m_Name{name}, m_Range{dateTime}, m_Metadata{metadata}, m_DataSeries{nullptr}
    {
    }

    QString m_Name;

    SqpRange m_Range;
    SqpRange m_CacheRange;
    QVariantHash m_Metadata;
    std::unique_ptr<IDataSeries> m_DataSeries;
};

Variable::Variable(const QString &name, const SqpRange &dateTime, const QVariantHash &metadata)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, dateTime, metadata)}
{
}

QString Variable::name() const noexcept
{
    return impl->m_Name;
}

SqpRange Variable::range() const noexcept
{
    return impl->m_Range;
}

void Variable::setRange(const SqpRange &range) noexcept
{
    impl->m_Range = range;
}

SqpRange Variable::cacheRange() const noexcept
{
    return impl->m_CacheRange;
}

void Variable::setCacheRange(const SqpRange &cacheRange) noexcept
{
    impl->m_CacheRange = cacheRange;
}

void Variable::setDataSeries(std::shared_ptr<IDataSeries> dataSeries) noexcept
{
    qCDebug(LOG_Variable()) << "Variable::setDataSeries" << QThread::currentThread()->objectName();
    if (!dataSeries) {
        /// @todo ALX : log
        return;
    }

    // Inits the data series of the variable
    if (!impl->m_DataSeries) {
        impl->m_DataSeries = dataSeries->clone();
    }
    else {
        impl->m_DataSeries->merge(dataSeries.get());
    }
}

IDataSeries *Variable::dataSeries() const noexcept
{
    return impl->m_DataSeries.get();
}

QVariantHash Variable::metadata() const noexcept
{
    return impl->m_Metadata;
}

bool Variable::contains(const SqpRange &range) const noexcept
{
    return impl->m_Range.contains(range);
}

bool Variable::intersect(const SqpRange &range) const noexcept
{
    return impl->m_Range.intersect(range);
}

bool Variable::isInside(const SqpRange &range) const noexcept
{
    return range.contains(SqpRange{impl->m_Range.m_TStart, impl->m_Range.m_TEnd});
}

bool Variable::cacheContains(const SqpRange &range) const noexcept
{
    return impl->m_CacheRange.contains(range);
}

bool Variable::cacheIntersect(const SqpRange &range) const noexcept
{
    return impl->m_CacheRange.intersect(range);
}

bool Variable::cacheIsInside(const SqpRange &range) const noexcept
{
    return range.contains(SqpRange{impl->m_CacheRange.m_TStart, impl->m_CacheRange.m_TEnd});
}


QVector<SqpRange> Variable::provideNotInCacheRangeList(const SqpRange &range)
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
                       << SqpRange{impl->m_CacheRange.m_TEnd, range.m_TStart};
        }
        else if (range.m_TStart < impl->m_CacheRange.m_TEnd) {
            notInCache << SqpRange{impl->m_CacheRange.m_TEnd, range.m_TStart};
        }
        else {
            qCCritical(LOG_Variable()) << tr("Detection of unknown case.")
                                       << QThread::currentThread();
        }
    }

    return notInCache;
}
