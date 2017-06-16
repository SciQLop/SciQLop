#include <Data/ScalarSeries.h>

ScalarSeries::ScalarSeries(int size, Unit xAxisUnit, Unit valuesUnit)
        : DataSeries{std::make_shared<ArrayData<1> >(size), std::move(xAxisUnit),
                     std::make_shared<ArrayData<1> >(size), std::move(valuesUnit)}
{
}

void ScalarSeries::setData(int index, double x, double value) noexcept
{
    xAxisData()->setData(index, x);
    valuesData()->setData(index, value);
}
