#include <Data/ScalarSeries.h>

ScalarSeries::ScalarSeries(std::vector<double> xAxisData, std::vector<double> valuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<1> >(std::move(valuesData)), valuesUnit}
{
}

std::unique_ptr<IDataSeries> ScalarSeries::clone() const
{
    return std::make_unique<ScalarSeries>(*this);
}

std::shared_ptr<IDataSeries> ScalarSeries::subDataSeries(const DateTimeRange &range)
{
    auto subXAxisData = std::vector<double>();
    auto subValuesData = std::vector<double>();
    this->lockRead();
    {
        auto bounds = xAxisRange(range.m_TStart, range.m_TEnd);
        for (auto it = bounds.first; it != bounds.second; ++it) {
            subXAxisData.push_back(it->x());
            subValuesData.push_back(it->value());
        }
    }
    this->unlock();

    return std::make_shared<ScalarSeries>(std::move(subXAxisData), std::move(subValuesData),
                                          this->xAxisUnit(), this->valuesUnit());
}
