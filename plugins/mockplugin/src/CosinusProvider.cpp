#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>

#include <cmath>

Q_LOGGING_CATEGORY(LOG_CosinusProvider, "CosinusProvider")

std::unique_ptr<IDataSeries>
CosinusProvider::retrieveData(const DataProviderParameters &parameters) const
{
    auto dateTime = parameters.m_Time;

    // Gets the timerange from the parameters
    auto start = dateTime.m_TStart;
    auto end = dateTime.m_TEnd;

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second)
    auto scalarSeries
        = std::make_unique<ScalarSeries>(end - start, Unit{QStringLiteral("t"), true}, Unit{});

    auto dataIndex = 0;
    for (auto time = start; time < end; ++time, ++dataIndex) {
        scalarSeries->setData(dataIndex, time, std::cos(time));
    }

    return scalarSeries;
}

void CosinusProvider::requestDataLoading(const QVector<SqpDateTime> &dateTimeList)
{
    // NOTE: Try to use multithread if possible
    for (const auto &dateTime : dateTimeList) {

        auto scalarSeries = this->retrieveDataSeries(dateTime);

        emit dataProvided(scalarSeries, dateTime);
    }
}


std::shared_ptr<IDataSeries> CosinusProvider::retrieveDataSeries(const SqpDateTime &dateTime)
{

    // Gets the timerange from the parameters
    auto start = dateTime.m_TStart;
    auto end = dateTime.m_TEnd;

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second)
    auto scalarSeries
        = std::make_shared<ScalarSeries>(end - start, Unit{QStringLiteral("t"), true}, Unit{});

    auto dataIndex = 0;
    for (auto time = start; time < end; ++time, ++dataIndex) {
        scalarSeries->setData(dataIndex, time, std::cos(time));
    }


    return scalarSeries;
}
