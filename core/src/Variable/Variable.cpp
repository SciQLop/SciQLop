#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpRange.h>

#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const SqpRange &dateTime,
                             const QVariantHash &metadata)
            : m_Name{name}, m_DateTime{dateTime}, m_Metadata{metadata}, m_DataSeries{nullptr}
    {
    }

    QString m_Name;

    SqpRange m_DateTime; // The dateTime available in the view and loaded. not the cache.
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

SqpRange Variable::dateTime() const noexcept
{
    return impl->m_DateTime;
}

void Variable::setDateTime(const SqpRange &dateTime) noexcept
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
        impl->m_DataSeries->merge(dataSeries.get());
        //  emit updated();
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

bool Variable::contains(const SqpRange &dateTime) const noexcept
{
    return impl->m_DateTime.contains(dateTime);
}

bool Variable::intersect(const SqpRange &dateTime) const noexcept
{
    return impl->m_DateTime.intersect(dateTime);
}

bool Variable::isInside(const SqpRange &dateTime) const noexcept
{
    return dateTime.contains(SqpRange{impl->m_DateTime.m_TStart, impl->m_DateTime.m_TEnd});
}
