#ifndef SCIQLOP_SCALARSERIES_H
#define SCIQLOP_SCALARSERIES_H

#include <Data/DataSeries.h>

/**
 * @brief The ScalarSeries class is the implementation for a data series representing a scalar.
 */
class ScalarSeries : public DataSeries<1> {
public:
    /**
     * Ctor with two vectors. The vectors must have the same size, otherwise a ScalarSeries with no
     * values will be created.
     * @param xAxisData x-axis data
     * @param valuesData values data
     */
    explicit ScalarSeries(QVector<double> xAxisData, QVector<double> valuesData,
                          const Unit &xAxisUnit, const Unit &valuesUnit);

    std::unique_ptr<IDataSeries> clone() const;
};

#endif // SCIQLOP_SCALARSERIES_H
