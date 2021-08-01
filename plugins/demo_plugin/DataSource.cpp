#include "DataSource.hpp"
#include "SqpApplication.h"
#include "DataSource/DataSourceItem.h"
#include "DataSource/datasources.h"

DataSource::DataSource()
{
    auto& dataSources = sqpApp->dataSources();
    auto id = this->id();
    auto data_source_name = this->name();
    dataSources.addDataSourceItem(id, "/DemoPlugin/DataSource/product", {{"type","scalar"}});
}

TimeSeries::ITimeSerie *DataSource::getData(const DataProviderParameters &parameters)
{
    std::size_t size =
        static_cast<std::size_t>(floor(parameters.m_Range.m_TEnd) -
            ceil(parameters.m_Range.m_TStart) + 1.);
    auto serie = new ScalarTimeSerie(size);
    std::generate(std::begin(*serie), std::end(*serie),
        [i = ceil(parameters.m_Range.m_TStart)]() mutable {
            return std::pair<double, double>{i, cos(i++ / 10.)};
        });
    return serie;
}
