#include "Data/VectorSeries.h"

namespace {

/**
 * Flatten the three components of a vector to a single QVector that can be passed to an ArrayData
 *
 * Example:
 * xValues = {1, 2, 3}
 * yValues = {4, 5, 6}
 * zValues = {7, 8, 9}
 *
 * result = {1, 4, 7, 2, 5, 8, 3, 6, 9}
 *
 * @param xValues the x-component values of the vector
 * @param yValues the y-component values of the vector
 * @param zValues the z-component values of the vector
 * @return the single QVector
 * @remarks the three components are consumed
 * @sa ArrayData
 */
std::vector<double> flatten(std::vector<double> xValues, std::vector<double> yValues,
                            std::vector<double> zValues)
{
    if (xValues.size() != yValues.size() || xValues.size() != zValues.size()) {
        /// @todo ALX : log
        return {};
    }

    auto result = std::vector<double>();
    result.reserve(xValues.size() * 3);
    for (auto i = 0u; i < xValues.size(); ++i) {
        result.push_back(xValues[i]);
        result.push_back(yValues[i]);
        result.push_back(zValues[i]);
    }

    return result;
}

} // namespace

VectorSeries::VectorSeries(std::vector<double> xAxisData, std::vector<double> xValuesData,
                           std::vector<double> yValuesData, std::vector<double> zValuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : VectorSeries{std::move(xAxisData), flatten(std::move(xValuesData), std::move(yValuesData),
                                                     std::move(zValuesData)),
                       xAxisUnit, valuesUnit}
{
}

VectorSeries::VectorSeries(std::vector<double> xAxisData, std::vector<double> valuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<2> >(std::move(valuesData), 3), valuesUnit}
{
}

std::unique_ptr<IDataSeries> VectorSeries::clone() const
{
    return std::make_unique<VectorSeries>(*this);
}

std::shared_ptr<IDataSeries> VectorSeries::subDataSeries(const DateTimeRange &range)
{
    auto subXAxisData = std::vector<double>();
    auto subValuesData = std::vector<double>();

    this->lockRead();
    {
        auto bounds = xAxisRange(range.m_TStart, range.m_TEnd);
        for (auto it = bounds.first; it != bounds.second; ++it) {
            subXAxisData.push_back(it->x());
            subValuesData.push_back(it->value(0));
            subValuesData.push_back(it->value(1));
            subValuesData.push_back(it->value(2));
        }
    }
    this->unlock();

    return std::make_shared<VectorSeries>(std::move(subXAxisData), std::move(subValuesData),
                                          this->xAxisUnit(), this->valuesUnit());
}
