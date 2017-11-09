#include "Data/DataSeriesUtils.h"

Q_LOGGING_CATEGORY(LOG_DataSeriesUtils, "DataSeriesUtils")

void DataSeriesUtils::fillDataHoles(std::vector<double> &xAxisData, std::vector<double> &valuesData,
                                    double resolution, double fillValue)
{
    if (resolution == 0. || std::isnan(resolution)) {
        qCWarning(LOG_DataSeriesUtils())
            << "Can't fill data holes with a null resolution, no changes will be made";
        return;
    }

    if (xAxisData.empty()) {
        qCWarning(LOG_DataSeriesUtils())
            << "Can't fill data holes for empty data, no changes will be made";
        return;
    }

    // Gets the number of values per x-axis data
    auto nbComponents = valuesData.size() / xAxisData.size();

    // Generates fill values that will be used to complete values data
    std::vector<double> fillValues(nbComponents, fillValue);

    // Traverses the x-axis data
    auto xAxisIt = xAxisData.begin();
    while (xAxisIt != xAxisData.end()) {
        // Stops at first value which has a gap greater than resolution with the value next to it
        xAxisIt = std::adjacent_find(
            xAxisIt, xAxisData.end(),
            [resolution](const auto &a, const auto &b) { return (b - a) > resolution; });

        if (xAxisIt != xAxisData.end()) {
            auto nextXAxisIt = xAxisIt + 1;

            // Gets the values that has a gap greater than resolution between them
            auto lowValue = *xAxisIt;
            auto highValue = *nextXAxisIt;

            // Completes holes between the two values by creating new values (according to the
            // resolution)
            for (auto i = lowValue + resolution; i < highValue; i += resolution) {
                // Gets the iterator of values data from which to insert fill values
                auto nextValuesIt = valuesData.begin()
                                    + std::distance(xAxisData.begin(), nextXAxisIt) * nbComponents;

                // New value is inserted before nextXAxisIt
                nextXAxisIt = xAxisData.insert(nextXAxisIt, i) + 1;

                // New values are inserted before nextValuesIt
                valuesData.insert(nextValuesIt, fillValues.begin(), fillValues.end());
            }

            // Moves to the next value to continue loop on the x-axis data
            xAxisIt = nextXAxisIt;
        }
    }
}
