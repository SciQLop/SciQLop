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
