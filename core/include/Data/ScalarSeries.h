#ifndef SCIQLOP_SCALARSERIES_H
#define SCIQLOP_SCALARSERIES_H

#include "CoreGlobal.h"

#include <Data/DataSeries.h>

/**
 * @brief The ScalarSeries class is the implementation for a data series representing a scalar.
 */
class SCIQLOP_CORE_EXPORT ScalarSeries : public DataSeries<1> {
public:
    /**
     * Ctor with two vectors. The vectors must have the same size, otherwise a ScalarSeries with no
     * values will be created.
     * @param xAxisData x-axis data
     * @param valuesData values data
     */
    explicit ScalarSeries(std::vector<double> xAxisData, std::vector<double> valuesData,
                          const Unit &xAxisUnit, const Unit &valuesUnit);

    std::unique_ptr<IDataSeries> clone() const override;

    std::shared_ptr<IDataSeries> subDataSeries(const DateTimeRange &range) override;
};

#endif // SCIQLOP_SCALARSERIES_H
