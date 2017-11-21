#ifndef SCIQLOP_DATASERIESUTILS_H
#define SCIQLOP_DATASERIESUTILS_H

#include "CoreGlobal.h"

#include <Common/SortUtils.h>
#include <Data/DataSeriesIterator.h>

#include <QLoggingCategory>
#include <cmath>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSeriesUtils)

/**
 * Utility class with methods for data series
 */
struct SCIQLOP_CORE_EXPORT DataSeriesUtils {
    /**
     * Define a meshs.
     *
     * A mesh is a regular grid representing cells of the same width (in x) and of the same height
     * (in y). At each mesh point is associated a value.
     *
     * Each axis of the mesh is defined by a minimum value, a number of values is a mesh step.
     * For example: if min = 1, nbValues = 5 and step = 2 => the axis of the mesh will be [1, 3, 5,
     * 7, 9].
     *
     * The values are defined in an array of size {nbX * nbY}. The data is stored along the X axis.
     *
     * For example, the mesh:
     * Y = 2 [  7   ;   8   ;   9
     * Y = 1    4   ;   5   ;   6
     * Y = 0    1   ;   2   ;   3   ]
     *        X = 0   X = 1   X = 2
     *
     * will be represented by data [1, 2, 3, 4, 5, 6, 7, 8, 9]
     */
    struct Mesh {
        explicit Mesh() = default;
        explicit Mesh(int nbX, double xMin, double xStep, int nbY, double yMin, double yStep)
                : m_NbX{nbX},
                  m_XMin{xMin},
                  m_XStep{xStep},
                  m_NbY{nbY},
                  m_YMin{yMin},
                  m_YStep{yStep},
                  m_Data(nbX * nbY)
        {
        }

        inline bool isEmpty() const { return m_Data.size() == 0; }
        inline double xMax() const { return m_XMin + (m_NbX - 1) * m_XStep; }
        inline double yMax() const { return m_YMin + (m_NbY - 1) * m_YStep; }

        int m_NbX{0};
        double m_XMin{};
        double m_XStep{};
        int m_NbY{0};
        double m_YMin{};
        double m_YStep{};
        std::vector<double> m_Data{};
    };

    /**
     * Represents a resolution used to generate the data of a mesh on the x-axis or in Y.
     *
     * A resolution is represented by a value and flag indicating if it's in the logarithmic scale
     * @sa Mesh
     */
    struct Resolution {
        double m_Val{std::numeric_limits<double>::quiet_NaN()};
        bool m_Logarithmic{false};
    };

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
     * It is also possible to set bounds for the data series. If these bounds are defined and exceed
     * the limits of the data series, data holes are added to the series at the beginning and/or the
     * end.
     *
     * The generation of data holes at the beginning/end of the data series is performed starting
     * from the x-axis series limit and adding data holes at each 'resolution step' as long as the
     * new bound is not reached.
     *
     * For example, with :
     * - xAxisData =  [3,    4,    5,    6,    7  ]
     * - valuesData = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
     * - fillValue = NaN
     * - minBound = 0
     * - maxBound = 12
     * - and resolution = 2;
     *
     * => Starting from 3 and decreasing 2 by 2 until reaching 0 : a data hole at value 1 will be
     * added to the beginning of the series
     * => Starting from 7 and increasing 2 by 2 until reaching 12 : data holes at values 9 and 11
     * will be added to the end of the series
     *
     * So :
     * => xAxisData =  [1,        3,    4,    5,    6,    7,    9,        11      ]
     * => valuesData = [NaN, NaN, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, NaN, NaN, NaN, NaN]
     *
     * @param xAxisData the x-axis data of the data series
     * @param valuesData the values data of the data series
     * @param resolution the resoultion (on x-axis) used to determinate data holes
     * @param fillValue the fill value used for data holes in the values data
     * @param minBound the limit at which to start filling data holes for the series. If set to NaN,
     * the limit is not used
     * @param maxBound the limit at which to end filling data holes for the series. If set to NaN,
     * the limit is not used
     *
     * @remarks There is no control over the consistency between x-axis data and values data. The
     * method considers that the data is well formed (the total number of values data is a multiple
     * of the number of x-axis data)
     */
    static void fillDataHoles(std::vector<double> &xAxisData, std::vector<double> &valuesData,
                              double resolution,
                              double fillValue = std::numeric_limits<double>::quiet_NaN(),
                              double minBound = std::numeric_limits<double>::quiet_NaN(),
                              double maxBound = std::numeric_limits<double>::quiet_NaN());
    /**
     * Computes the resolution of a dataset passed as a parameter.
     *
     * The resolution of a dataset is the minimum difference between two values that follow in the
     * set.
     * For example:
     * - for the set [0, 2, 4, 8, 10, 11, 13] => the resolution is 1 (difference between 10 and 11).
     *
     * A resolution can be calculated on the logarithmic scale (base of 10). In this case, the
     * dataset is first converted to logarithmic values.
     * For example:
     * - for the set [10, 100, 10000, 1000000], the values are converted to [1, 2, 4, 6] => the
     * logarithmic resolution is 1 (difference between 1 and 2).
     *
     * @param begin the iterator pointing to the beginning of the dataset
     * @param end the iterator pointing to the end of the dataset
     * @param logarithmic computes a logarithmic resolution or not
     * @return the resolution computed
     * @warning the method considers the dataset as sorted and doesn't control it.
     */
    template <typename Iterator>
    static Resolution resolution(Iterator begin, Iterator end, bool logarithmic = false);

    /**
     * Computes a regular mesh for a data series, according to resolutions for x-axis and y-axis
     * passed as parameters.
     *
     * The mesh is created from the resolutions in x and y and the boundaries delimiting the data
     * series. If the resolutions do not allow to obtain a regular mesh, they are recalculated.
     *
     * For example :
     * Let x-axis data = [0, 1, 3, 5, 9], its associated values ​​= [0, 10, 30, 50, 90] and
     * xResolution = 2.
     * Based on the resolution, the mesh would be [0, 2, 4, 6, 8, 10] and would be invalid because
     * it exceeds the maximum bound of the data. The resolution is thus recalculated so that the
     * mesh holds between the data terminals.
     * So => resolution is 1.8 and the mesh is [0, 1.8, 3.6, 5.4, 7.2, 9].
     *
     * Once the mesh is generated in x and y, the values ​​are associated with each mesh point,
     * based on the data in the series, finding the existing data at which the mesh point would be
     * or would be closest to, without exceeding it.
     *
     * In the example, we determine the value of each mesh point:
     * - x = 0 => value = 0 (existing x in the data series)
     * - x = 1.8 => value = 10 (the closest existing x: 1)
     * - x = 3.6 => value = 30 (the closest existing x: 3)
     * - x = 5.4 => value = 50 (the closest existing x: 5)
     * - x = 7.2 => value = 50 (the closest existing x: 5)
     * - x = 9 => value = 90 (existing x in the data series)
     *
     * Same algorithm is applied for y-axis.
     *
     * @param begin the iterator pointing to the beginning of the data series
     * @param end the iterator pointing to the end of the data series
     * @param xResolution the resolution expected for the mesh's x-axis
     * @param yResolution the resolution expected for the mesh's y-axis
     * @return the mesh created, an empty mesh if the input data do not allow to generate a regular
     * mesh (empty data, null resolutions, logarithmic x-axis)
     * @warning the method considers the dataset as sorted and doesn't control it.
     */
    static Mesh regularMesh(DataSeriesIterator begin, DataSeriesIterator end,
                            Resolution xResolution, Resolution yResolution);

    /**
     * Calculates the min and max thresholds of a dataset.
     *
     * The thresholds of a dataset correspond to the min and max limits of the set to which the
     * outliers are exluded (values distant from the others) For example, for the set [1, 2, 3, 4,
     * 5, 10000], 10000 is an outlier and will be excluded from the thresholds.
     *
     * Bounds determining the thresholds is calculated according to the mean and the standard
     * deviation of the defined data. The thresholds are limited to the min / max values of the
     * dataset: if for example the calculated min threshold is 2 but the min value of the datasetset
     * is 4, 4 is returned as the min threshold.
     *
     * @param begin the beginning of the dataset
     * @param end the end of the dataset
     * @param logarithmic computes threshold with a logarithmic scale or not
     * @return the thresholds computed, a couple of nan values if it couldn't be computed
     */
    template <typename Iterator>
    static std::pair<double, double> thresholds(Iterator begin, Iterator end,
                                                bool logarithmic = false);
};

template <typename Iterator>
DataSeriesUtils::Resolution DataSeriesUtils::resolution(Iterator begin, Iterator end,
                                                        bool logarithmic)
{
    // Retrieves data into a work dataset
    using ValueType = typename Iterator::value_type;
    std::vector<ValueType> values{};
    std::copy(begin, end, std::back_inserter(values));

    // Converts data if logarithmic flag is activated
    if (logarithmic) {
        std::for_each(values.begin(), values.end(),
                      [logarithmic](auto &val) { val = std::log10(val); });
    }

    // Computes the differences between the values in the dataset
    std::adjacent_difference(values.begin(), values.end(), values.begin());

    // Retrieves the smallest difference
    auto resolutionIt = std::min_element(values.begin(), values.end());
    auto resolution
        = resolutionIt != values.end() ? *resolutionIt : std::numeric_limits<double>::quiet_NaN();

    return Resolution{resolution, logarithmic};
}

template <typename Iterator>
std::pair<double, double> DataSeriesUtils::thresholds(Iterator begin, Iterator end,
                                                      bool logarithmic)
{
    /// Lambda that converts values in case of logaritmic scale
    auto toLog = [logarithmic](const auto &value) {
        if (logarithmic) {
            // Logaritmic scale doesn't include zero value
            return !(std::isnan(value) || value < std::numeric_limits<double>::epsilon())
                       ? std::log10(value)
                       : std::numeric_limits<double>::quiet_NaN();
        }
        else {
            return value;
        }
    };

    /// Lambda that converts values to linear scale
    auto fromLog
        = [logarithmic](const auto &value) { return logarithmic ? std::pow(10, value) : value; };

    /// Lambda used to sum data and divide the sum by the number of data. It is used to calculate
    /// the mean and standard deviation
    /// @param fun the data addition function
    auto accumulate = [begin, end](auto fun) {
        double sum;
        int nbValues;
        std::tie(sum, nbValues) = std::accumulate(
            begin, end, std::make_pair(0., 0), [fun](const auto &input, const auto &value) {
                auto computedValue = fun(value);

                // NaN values are excluded from the sum
                return !std::isnan(computedValue)
                           ? std::make_pair(input.first + computedValue, input.second + 1)
                           : input;
            });

        return nbValues != 0 ? sum / nbValues : std::numeric_limits<double>::quiet_NaN();
    };

    // Computes mean
    auto mean = accumulate([toLog](const auto &val) { return toLog(val); });
    if (std::isnan(mean)) {
        return {std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN()};
    }

    // Computes standard deviation
    auto variance
        = accumulate([mean, toLog](const auto &val) { return std::pow(toLog(val) - mean, 2); });
    auto sigma = std::sqrt(variance);

    // Computes thresholds
    auto minThreshold = fromLog(mean - 3 * sigma);
    auto maxThreshold = fromLog(mean + 3 * sigma);

    // Finds min/max values
    auto minIt = std::min_element(begin, end, [toLog](const auto &it1, const auto &it2) {
        return SortUtils::minCompareWithNaN(toLog(it1), toLog(it2));
    });
    auto maxIt = std::max_element(begin, end, [toLog](const auto &it1, const auto &it2) {
        return SortUtils::maxCompareWithNaN(toLog(it1), toLog(it2));
    });

    // Returns thresholds (bounded to min/max values)
    return {std::max(*minIt, minThreshold), std::min(*maxIt, maxThreshold)};
}

#endif // SCIQLOP_DATASERIESUTILS_H
