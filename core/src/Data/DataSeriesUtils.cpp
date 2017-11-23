#include "Data/DataSeriesUtils.h"

Q_LOGGING_CATEGORY(LOG_DataSeriesUtils, "DataSeriesUtils")

void DataSeriesUtils::fillDataHoles(std::vector<double> &xAxisData, std::vector<double> &valuesData,
                                    double resolution, double fillValue, double minBound,
                                    double maxBound)
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

    // Checks if there are data holes on the beginning of the data and generates the hole at the
    // extremity if it's the case
    auto minXAxisData = xAxisData.front();
    if (!std::isnan(minBound) && minBound < minXAxisData) {
        auto holeSize = static_cast<int>((minXAxisData - minBound) / resolution);
        if (holeSize > 0) {
            xAxisData.insert(xAxisData.begin(), minXAxisData - holeSize * resolution);
            valuesData.insert(valuesData.begin(), fillValues.begin(), fillValues.end());
        }
    }

    // Same for the end of the data
    auto maxXAxisData = xAxisData.back();
    if (!std::isnan(maxBound) && maxBound > maxXAxisData) {
        auto holeSize = static_cast<int>((maxBound - maxXAxisData) / resolution);
        if (holeSize > 0) {
            xAxisData.insert(xAxisData.end(), maxXAxisData + holeSize * resolution);
            valuesData.insert(valuesData.end(), fillValues.begin(), fillValues.end());
        }
    }

    // Generates other data holes
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

namespace {

/**
 * Generates axis's mesh properties according to data and resolution
 * @param begin the iterator pointing to the beginning of the data
 * @param end the iterator pointing to the end of the data
 * @param fun the function to retrieve data from the data iterators
 * @param resolution the resolution to use for the axis' mesh
 * @return a tuple representing the mesh properties : <nb values, min value, value step>
 */
template <typename Iterator, typename IteratorFun>
std::tuple<int, double, double> meshProperties(Iterator begin, Iterator end, IteratorFun fun,
                                               double resolution)
{
    // Computes the gap between min and max data. This will be used to determinate the step between
    // each data of the mesh
    auto min = fun(begin);
    auto max = fun(end - 1);
    auto gap = max - min;

    // Computes the step trying to use the fixed resolution. If the resolution doesn't separate the
    // values evenly , it is recalculated.
    // For example, for a resolution of 2.0:
    // - for interval [0; 8] => resolution is valid, the generated mesh will be [0, 2, 4, 6, 8]
    // - for interval [0; 9] => it's impossible to create a regular mesh with this resolution
    // The resolution is recalculated and is worth 1.8. The generated mesh will be [0, 1.8, 3.6,
    // 5.4, 7.2, 9]
    auto nbVal = static_cast<int>(std::ceil(gap / resolution));
    auto step = gap / nbVal;

    // last data is included in the total number of values
    return std::make_tuple(nbVal + 1, min, step);
}

} // namespace

DataSeriesUtils::Mesh DataSeriesUtils::regularMesh(DataSeriesIterator begin, DataSeriesIterator end,
                                                   Resolution xResolution, Resolution yResolution)
{
    // Checks preconditions
    if (xResolution.m_Val == 0. || std::isnan(xResolution.m_Val) || yResolution.m_Val == 0.
        || std::isnan(yResolution.m_Val)) {
        qCWarning(LOG_DataSeriesUtils()) << "Can't generate mesh with a null resolution";
        return Mesh{};
    }

    if (xResolution.m_Logarithmic) {
        qCWarning(LOG_DataSeriesUtils())
            << "Can't generate mesh with a logarithmic x-axis resolution";
        return Mesh{};
    }

    if (std::distance(begin, end) == 0) {
        qCWarning(LOG_DataSeriesUtils()) << "Can't generate mesh for empty data";
        return Mesh{};
    }

    auto yData = begin->y();
    if (yData.empty()) {
        qCWarning(LOG_DataSeriesUtils()) << "Can't generate mesh for data with no y-axis";
        return Mesh{};
    }

    // Converts y-axis and its resolution to logarithmic values
    if (yResolution.m_Logarithmic) {
        std::for_each(yData.begin(), yData.end(), [](auto &val) { val = std::log10(val); });
    }

    // Computes mesh properties
    int nbX, nbY;
    double xMin, xStep, yMin, yStep;
    std::tie(nbX, xMin, xStep)
        = meshProperties(begin, end, [](const auto &it) { return it->x(); }, xResolution.m_Val);
    std::tie(nbY, yMin, yStep) = meshProperties(
        yData.begin(), yData.end(), [](const auto &it) { return *it; }, yResolution.m_Val);

    // Generates mesh according to the x-axis and y-axis steps
    Mesh result{nbX, xMin, xStep, nbY, yMin, yStep};

    for (auto meshXIndex = 0; meshXIndex < nbX; ++meshXIndex) {
        auto meshX = xMin + meshXIndex * xStep;
        // According to current x-axis of the mesh, finds in the data series the interval in which
        // the data is or gets closer (without exceeding it).
        // An interval is defined by a value and extends to +/- 50% of the resolution. For example,
        // for a value of 3 and a resolution of 1, the associated interval is [2.5, 3.5].
        auto xIt = std::lower_bound(begin, end, meshX,
                                    [xResolution](const auto &it, const auto &val) {
                                        return it.x() - xResolution.m_Val / 2. < val;
                                    })
                   - 1;

        // When the corresponding entry of the data series is found, generates the values of the
        // mesh by retrieving the values of the entry, for each y-axis value of the mesh
        auto values = xIt->values();

        for (auto meshYIndex = 0; meshYIndex < nbY; ++meshYIndex) {
            auto meshY = yMin + meshYIndex * yStep;

            auto yBegin = yData.begin();
            auto yIt = std::lower_bound(yBegin, yData.end(), meshY,
                                        [yResolution](const auto &it, const auto &val) {
                                            return it - yResolution.m_Val / 2. < val;
                                        })
                       - 1;

            auto valueIndex = std::distance(yBegin, yIt);
            result.m_Data[result.m_NbX * meshYIndex + meshXIndex] = values.at(valueIndex);
        }
    }

    return result;
}
