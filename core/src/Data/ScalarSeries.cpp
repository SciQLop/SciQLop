#include <Data/ScalarSeries.h>

ScalarSeries::ScalarSeries(int size, const Unit &xAxisUnit, const Unit &valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(size), xAxisUnit,
                     std::make_shared<ArrayData<1> >(size), valuesUnit}
{
}

void ScalarSeries::setData(int index, double x, double value) noexcept
{
    xAxisData()->setData(index, x);
    valuesData()->setData(index, value);
}