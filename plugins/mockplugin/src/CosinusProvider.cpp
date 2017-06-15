#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>

#include <cmath>

std::unique_ptr<IDataSeries>
CosinusProvider::retrieveData(const DataProviderParameters &parameters) const
{
    // Gets the timerange from the parameters
    auto start = parameters.m_TStart;
    auto end = parameters.m_TEnd;

    // We assure that timerange is valid
    if (end < start) {
        std::swap(start, end);
    }

    // Generates scalar series containing cosinus values (one value per second)
    auto scalarSeries
        = std::make_unique<ScalarSeries>(end - start, QStringLiteral("t"), QStringLiteral(""));

    for (auto time = start; time < end; ++time) {
        auto dataIndex = time - start;
        scalarSeries->setData(dataIndex, time, std::cos(time));
    }

    return scalarSeries;
}
