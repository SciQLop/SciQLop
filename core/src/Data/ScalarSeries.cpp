#include <Data/ScalarSeries.h>

ScalarSeries::ScalarSeries(QVector<double> xAxisData, QVector<double> valuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<1> >(std::move(valuesData)), valuesUnit}
{
}

std::unique_ptr<IDataSeries> ScalarSeries::clone() const
{
    return std::make_unique<ScalarSeries>(*this);
}

std::shared_ptr<IDataSeries> ScalarSeries::subData(const SqpRange &range)
{
    auto subXAxisData = QVector<double>();
    auto subValuesData = QVector<double>();
    this->lockRead();
    {
        const auto &currentXData = this->xAxisData()->cdata();
        const auto &currentValuesData = this->valuesData()->cdata();

        auto xDataBegin = currentXData.cbegin();
        auto xDataEnd = currentXData.cend();

        auto lowerIt = std::lower_bound(xDataBegin, xDataEnd, range.m_TStart);
        auto upperIt = std::upper_bound(xDataBegin, xDataEnd, range.m_TEnd);
        auto distance = std::distance(xDataBegin, lowerIt);

        auto valuesDataIt = currentValuesData.cbegin() + distance;
        for (auto xAxisDataIt = lowerIt; xAxisDataIt != upperIt; ++xAxisDataIt, ++valuesDataIt) {
            subXAxisData.append(*xAxisDataIt);
            subValuesData.append(*valuesDataIt);
        }
    }
    this->unlock();

    return std::make_shared<ScalarSeries>(subXAxisData, subValuesData, this->xAxisUnit(),
                                          this->valuesUnit());
}
