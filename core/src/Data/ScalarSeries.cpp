#include <Data/ScalarSeries.h>

ScalarSeries::ScalarSeries(int size, const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(size), xAxisUnit,
                     std::make_shared<ArrayData<1> >(size), valuesUnit}
{
}

ScalarSeries::ScalarSeries(QVector<double> xAxisData, QVector<double> valuesData,
                           const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(std::move(xAxisData)), xAxisUnit,
                     std::make_shared<ArrayData<1> >(std::move(valuesData)), valuesUnit}
{
}

void ScalarSeries::setData(int index, double x, double value) noexcept
{
    xAxisData()->setData(index, x);
    valuesData()->setData(index, value);
}

std::unique_ptr<IDataSeries> ScalarSeries::clone() const
{
    return std::make_unique<ScalarSeries>(*this);
}
