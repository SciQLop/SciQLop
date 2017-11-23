#include "DataSeriesTestsUtils.h"

void validateRange(DataSeriesIterator first, DataSeriesIterator last, const DataContainer &xData,
                   const DataContainer &valuesData)
{
    QVERIFY(std::equal(first, last, xData.cbegin(), xData.cend(),
                       [](const auto &it, const auto &expectedX) { return it.x() == expectedX; }));
    QVERIFY(std::equal(
        first, last, valuesData.cbegin(), valuesData.cend(),
        [](const auto &it, const auto &expectedVal) { return it.value() == expectedVal; }));
}

void validateRange(DataSeriesIterator first, DataSeriesIterator last, const DataContainer &xData, const std::vector<DataContainer> &valuesData)
{
    QVERIFY(std::equal(first, last, xData.cbegin(), xData.cend(),
                       [](const auto &it, const auto &expectedX) { return it.x() == expectedX; }));
    for (auto i = 0u; i < valuesData.size(); ++i) {
        auto componentData = valuesData.at(i);

        QVERIFY(std::equal(
                    first, last, componentData.cbegin(), componentData.cend(),
                    [i](const auto &it, const auto &expectedVal) { return it.value(i) == expectedVal; }));
    }
}
