#pragma once
#include <Data/IDataProvider.h>

class PyDataProvider : public IDataProvider
{
public:
    PyDataProvider() {}

    virtual TimeSeries::ITimeSerie getData(const std::string& key, double start_time, double stop_time)
    {}

    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters)
    {
        return nullptr;
    }
};
