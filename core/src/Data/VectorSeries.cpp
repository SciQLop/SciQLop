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
QVector<double> flatten(QVector<double> xValues, QVector<double> yValues, QVector<double> zValues)
{
    if (xValues.size() != yValues.size() || xValues.size() != zValues.size()) {
        /// @todo ALX : log
        return {};
    }

    auto result = QVector<double>{};
    result.reserve(xValues.size() * 3);

    while (!xValues.isEmpty()) {
        result.append({xValues.takeFirst(), yValues.takeFirst(), zValues.takeFirst()});
    }

    return result;
}

} // namespace

VectorSeries::VectorSeries(QVector<double> xAxisData, QVector<double> xValuesData,
                           QVector<double> yValuesData, QVector<double> zValuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : VectorSeries{std::move(xAxisData), flatten(std::move(xValuesData), std::move(yValuesData),
                                                     std::move(zValuesData)),
                       xAxisUnit, valuesUnit}
{
}

VectorSeries::VectorSeries(QVector<double> xAxisData, QVector<double> valuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<2> >(std::move(valuesData), 3), valuesUnit}
{
}

std::unique_ptr<IDataSeries> VectorSeries::clone() const
{
    return std::make_unique<VectorSeries>(*this);
}

std::shared_ptr<IDataSeries> VectorSeries::subDataSeries(const SqpRange &range)
{
    auto subXAxisData = QVector<double>();
    auto subXValuesData = QVector<double>();
    auto subYValuesData = QVector<double>();
    auto subZValuesData = QVector<double>();

    this->lockRead();
    {
        auto bounds = xAxisRange(range.m_TStart, range.m_TEnd);
        for (auto it = bounds.first; it != bounds.second; ++it) {
            subXAxisData.append(it->x());
            subXValuesData.append(it->value(0));
            subYValuesData.append(it->value(1));
            subZValuesData.append(it->value(2));
        }
    }
    this->unlock();

    return std::make_shared<VectorSeries>(subXAxisData, subXValuesData, subYValuesData,
                                          subZValuesData, this->xAxisUnit(), this->valuesUnit());
}
