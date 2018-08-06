#ifndef SCIQLOP_SPECTROGRAMSERIES_H
#define SCIQLOP_SPECTROGRAMSERIES_H

#include "CoreGlobal.h"

#include <Data/DataSeries.h>

/**
 * @brief The SpectrogramSeries class is the implementation for a data series representing a
 * spectrogram.
 *
 * It defines values on a x-axis and a y-axis.
 */
class SCIQLOP_CORE_EXPORT SpectrogramSeries : public DataSeries<2> {
public:
    /// Ctor
    explicit SpectrogramSeries(std::vector<double> xAxisData, std::vector<double> yAxisData,
                               std::vector<double> valuesData, const Unit &xAxisUnit,
                               const Unit &yAxisUnit, const Unit &valuesUnit,
                               double xResolution = std::numeric_limits<double>::quiet_NaN());

    /// Ctor directly with the y-axis
    explicit SpectrogramSeries(std::shared_ptr<ArrayData<1> > xAxisData, const Unit &xAxisUnit,
                               std::shared_ptr<ArrayData<2> > valuesData, const Unit &valuesUnit,
                               OptionalAxis yAxis,
                               double xResolution = std::numeric_limits<double>::quiet_NaN());

    /// @sa DataSeries::clone()
    std::unique_ptr<IDataSeries> clone() const override;

    /// @sa DataSeries::subDataSeries()
    std::shared_ptr<IDataSeries> subDataSeries(const DateTimeRange &range) override;

    inline double xResolution() const noexcept { return m_XResolution; }

private:
    double m_XResolution; ///< Resolution used on x-axis to build the spectrogram
};

#endif // SCIQLOP_SPECTROGRAMSERIES_H
