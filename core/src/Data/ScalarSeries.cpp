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

std::shared_ptr<IDataSeries> ScalarSeries::subDataSeries(const SqpRange &range)
{
    auto subXAxisData = QVector<double>();
    auto subValuesData = QVector<double>();
    this->lockRead();
    {
        auto bounds = subData(range.m_TStart, range.m_TEnd);
        for (auto it = bounds.first; it != bounds.second; ++it) {
            subXAxisData.append(it->x());
            subValuesData.append(it->value());
        }
    }
    this->unlock();

    return std::make_shared<ScalarSeries>(subXAxisData, subValuesData, this->xAxisUnit(),
                                          this->valuesUnit());
}
