#ifndef SCIQLOP_SCALARSERIES_H
#define SCIQLOP_SCALARSERIES_H

#include <Data/DataSeries.h>

/**
 * @brief The ScalarSeries class is the implementation for a data series representing a scalar.
 */
class ScalarSeries : public DataSeries<1> {
public:
    /**
     * Ctor
     * @param size the number of data the series will hold
     * @param xAxisUnit x-axis unit
     * @param valuesUnit values unit
     */
    explicit ScalarSeries(int size, const Unit &xAxisUnit, const Unit &valuesUnit);

    /**
     * Sets data for a specific index. The index has to be valid to be effective
     * @param index the index to which the data will be set
     * @param x the x-axis data
     * @param value the value data
     */
    void setData(int index, double x, double value) noexcept;

    std::unique_ptr<IDataSeries> clone() const;
};

#endif // SCIQLOP_SCALARSERIES_H
