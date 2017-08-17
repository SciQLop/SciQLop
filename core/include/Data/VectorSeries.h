#ifndef SCIQLOP_VECTORSERIES_H
#define SCIQLOP_VECTORSERIES_H

#include "CoreGlobal.h"

#include <Data/DataSeries.h>

/**
 * @brief The VectorSeries class is the implementation for a data series representing a vector.
 */
class SCIQLOP_CORE_EXPORT VectorSeries : public DataSeries<2> {
public:
    /**
     * Ctor. The vectors must have the same size, otherwise a ScalarSeries with no values will be
     * created.
     * @param xAxisData x-axis data
     * @param xvaluesData x-values data
     * @param yvaluesData y-values data
     * @param zvaluesData z-values data
     */
    explicit VectorSeries(QVector<double> xAxisData, QVector<double> xValuesData,
                          QVector<double> yValuesData, QVector<double> zValuesData,
                          const Unit &xAxisUnit, const Unit &valuesUnit);

    std::unique_ptr<IDataSeries> clone() const;

    std::shared_ptr<IDataSeries> subDataSeries(const SqpRange &range) override;
};

#endif // SCIQLOP_VECTORSERIES_H
