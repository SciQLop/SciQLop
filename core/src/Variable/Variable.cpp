#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpDateTime.h>

#include <QReadWriteLock>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_Variable, "Variable")

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const QString &unit, const QString &mission,
                             const SqpDateTime &dateTime)
            : m_Name{name},
              m_Unit{unit},
              m_Mission{mission},
              m_DateTime{dateTime},
              m_DataSeries{nullptr}
    {
    }

    QString m_Name;
    QString m_Unit;
    QString m_Mission;

    SqpDateTime m_DateTime; // The dateTime available in the view and loaded. not the cache.
    std::unique_ptr<IDataSeries> m_DataSeries;
};

Variable::Variable(const QString &name, const QString &unit, const QString &mission,
                   const SqpDateTime &dateTime)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, unit, mission, dateTime)}
{
}

QString Variable::name() const noexcept
{
    return impl->m_Name;
}

QString Variable::mission() const noexcept
{
    return impl->m_Mission;
}

QString Variable::unit() const noexcept
{
    return impl->m_Unit;
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
    qCInfo(LOG_Variable()) << "Variable::setDataSeries" << QThread::currentThread()->objectName();
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
