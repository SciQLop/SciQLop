#ifndef SCIQLOP_DATASERIESUTILS_H
#define SCIQLOP_DATASERIESUTILS_H

#include "CoreGlobal.h"

#include <QLoggingCategory>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSeriesUtils)

/**
 * Utility class with methods for data series
 */
struct SCIQLOP_CORE_EXPORT DataSeriesUtils {
    /**
     * Processes data from a data series to complete the data holes with a fill value.
     *
     * A data hole is determined by the resolution passed in parameter: if, between two continuous
     * data on the x-axis, the difference between these data is greater than the resolution, then
     * there is one or more holes between them. The holes are filled by adding:
     * - for the x-axis, new data corresponding to the 'step resolution' starting from the first
     * data;
     * - for values, a default value (fill value) for each new data added on the x-axis.
     *
     * For example, with :
     * - xAxisData =  [0,    1,    5,    7,    14  ]
     * - valuesData = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] (two components per x-axis data)
     * - fillValue = NaN
     * - and resolution = 2;
     *
     * For the x axis, we calculate as data holes: [3, 9, 11, 13]. These holes are added to the
     * x-axis data, and NaNs (two per x-axis data) are added to the values:
     * => xAxisData =  [0,    1,    3,        5,    7,    9,        11,       13,       14  ]
     * => valuesData = [0, 1, 2, 3, NaN, NaN, 4, 5, 6, 7, NaN, NaN, NaN, NaN, NaN, NaN, 8, 9]
     *
     * @param xAxisData the x-axis data of the data series
     * @param valuesData the values data of the data series
     * @param resolution the resoultion (on x-axis) used to determinate data holes
     * @param fillValue the fill value used for data holes in the values data
     *
     * @remarks There is no control over the consistency between x-axis data and values data. The
     * method considers that the data is well formed (the total number of values data is a multiple
     * of the number of x-axis data)
     */
    static void fillDataHoles(std::vector<double> &xAxisData, std::vector<double> &valuesData,
                              double resolution,
                              double fillValue = std::numeric_limits<double>::quiet_NaN());
};

#endif // SCIQLOP_DATASERIESUTILS_H
