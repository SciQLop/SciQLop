#include <Data/SpectrogramSeries.h>

SpectrogramSeries::SpectrogramSeries(std::vector<double> xAxisData, std::vector<double> yAxisData,
                                     std::vector<double> valuesData, const Unit &xAxisUnit,
                                     const Unit &yAxisUnit, const Unit &valuesUnit,
                                     double resolution)
        : SpectrogramSeries{
              std::make_shared<ArrayData<1> >(std::move(xAxisData)),
              xAxisUnit,
              std::make_shared<ArrayData<2> >(std::move(valuesData), yAxisData.size()),
              valuesUnit,
              OptionalAxis{std::make_shared<ArrayData<1> >(std::move(yAxisData)), yAxisUnit},
              resolution}
{
}

SpectrogramSeries::SpectrogramSeries(std::shared_ptr<ArrayData<1> > xAxisData,
                                     const Unit &xAxisUnit,
                                     std::shared_ptr<ArrayData<2> > valuesData,
                                     const Unit &valuesUnit, OptionalAxis yAxis, double resolution)
        : DataSeries{std::move(xAxisData), xAxisUnit, std::move(valuesData), valuesUnit,
                     std::move(yAxis)},
          m_XResolution{resolution}
{
}

std::unique_ptr<IDataSeries> SpectrogramSeries::clone() const
{
    return std::make_unique<SpectrogramSeries>(*this);
}

std::shared_ptr<IDataSeries> SpectrogramSeries::subDataSeries(const DateTimeRange &range)
{
    auto subXAxisData = std::vector<double>();
    auto subValuesData = QVector<double>(); // Uses QVector to append easily values to it
    this->lockRead();
    auto bounds = xAxisRange(range.m_TStart, range.m_TEnd);
    for (auto it = bounds.first; it != bounds.second; ++it) {
        subXAxisData.push_back(it->x());
        subValuesData.append(it->values());
    }

    auto yAxis = this->yAxis();
    this->unlock();

    return std::make_shared<SpectrogramSeries>(
        std::make_shared<ArrayData<1> >(std::move(subXAxisData)), this->xAxisUnit(),
        std::make_shared<ArrayData<2> >(subValuesData.toStdVector(), yAxis.size()),
        this->valuesUnit(), std::move(yAxis));
}
