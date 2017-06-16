#include "Variable/Variable.h"

#include <Data/IDataSeries.h>

struct Variable::VariablePrivate {
    explicit VariablePrivate(const QString &name, const QString &unit, const QString &mission)
            : m_Name{name}, m_Unit{unit}, m_Mission{mission}, m_DataSeries{nullptr}
    {
    }

    QString m_Name;
    QString m_Unit;
    QString m_Mission;
    std::unique_ptr<IDataSeries> m_DataSeries;
};

Variable::Variable(const QString &name, const QString &unit, const QString &mission)
        : impl{spimpl::make_unique_impl<VariablePrivate>(name, unit, mission)}
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
