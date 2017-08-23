#include "Data/VectorSeries.h"

VectorSeries::VectorSeries(QVector<double> xAxisData, QVector<double> xValuesData,
                           QVector<double> yValuesData, QVector<double> zValuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<2> >(QVector<QVector<double> >{
                         std::move(xValuesData), std::move(yValuesData), std::move(zValuesData)}),
                     valuesUnit}
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
