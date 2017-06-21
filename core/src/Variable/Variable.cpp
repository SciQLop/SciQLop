#include "Variable/Variable.h"

#include <Data/IDataSeries.h>
#include <Data/SqpDateTime.h>

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

void Variable::addDataSeries(std::unique_ptr<IDataSeries> dataSeries) noexcept
{
    if (!impl->m_DataSeries) {
        impl->m_DataSeries = std::move(dataSeries);
    }
    /// @todo : else, merge the two data series (if possible)
}

IDataSeries *Variable::dataSeries() const noexcept
{
    return impl->m_DataSeries.get();
}

void Variable::onXRangeChanged(SqpDateTime dateTime)
{
    qCInfo(LOG_Variable()) << "onXRangeChanged detected";

    if (!impl->m_DateTime.contains(dateTime)) {
        // The current variable dateTime isn't enough to display the dateTime requested.
        // We have to update it to the new dateTime requested.
        // the correspondant new data to display will be given by the cache if possible and the
        // provider if necessary.
        qCInfo(LOG_Variable()) << "NEW DATE NEEDED";

        impl->m_DateTime = dateTime;
    }
}
