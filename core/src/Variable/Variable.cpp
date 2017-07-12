#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpDateTime.h>

#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const SqpDateTime &dateTime,
                             const QVariantHash &metadata)
            : m_Name{name}, m_DateTime{dateTime}, m_Metadata{metadata}, m_DataSeries{nullptr}
    {
    }

    QString m_Name;

    SqpDateTime m_DateTime; // The dateTime available in the view and loaded. not the cache.
    QVariantHash m_Metadata;
    std::unique_ptr<IDataSeries> m_DataSeries;
};

Variable::Variable(const QString &name, const SqpDateTime &dateTime, const QVariantHash &metadata)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, dateTime, metadata)}
{
}

QString Variable::name() const noexcept
{
    return impl->m_Name;
}

SqpDateTime Variable::dateTime() const noexcept
{
    return impl->m_DateTime;
}

void Variable::setDateTime(const SqpDateTime &dateTime) noexcept
{
    impl->m_DateTime = dateTime;
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
        dataSeries->lockWrite();
        impl->m_DataSeries->lockWrite();
        impl->m_DataSeries->merge(dataSeries.get());
        impl->m_DataSeries->unlock();
        dataSeries->unlock();
        emit updated();
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

bool Variable::contains(const SqpDateTime &dateTime) const noexcept
{
    return impl->m_DateTime.contains(dateTime);
}

bool Variable::intersect(const SqpDateTime &dateTime) const noexcept
{
    return impl->m_DateTime.intersect(dateTime);
}

bool Variable::isInside(const SqpDateTime &dateTime) const noexcept
{
    return dateTime.contains(SqpDateTime{impl->m_DateTime.m_TStart, impl->m_DateTime.m_TEnd});
}
