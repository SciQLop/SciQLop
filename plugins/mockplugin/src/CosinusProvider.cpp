#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>

#include <cmath>

#include <QDateTime>

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
    auto dataIndex = 0;

    // Gets the timerange from the parameters
    double freq = 100.0;
    double start = dateTime.m_TStart * freq; // 100 htz
    double end = dateTime.m_TEnd * freq;     // 100 htz

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second)
    auto scalarSeries
        = std::make_shared<ScalarSeries>(end - start, Unit{QStringLiteral("t"), true}, Unit{});

    for (auto time = start; time < end; ++time, ++dataIndex) {
        const auto timeOnFreq = time / freq;
        scalarSeries->setData(dataIndex, timeOnFreq, std::cos(timeOnFreq));
    }
    return scalarSeries;
}
