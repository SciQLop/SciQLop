/**
 * The DataSeriesTestsUtils file contains a set of utility methods that can be used to test the operations on a DataSeries.
 *
 * Most of these methods are template methods to adapt to any series (scalars, vectors, spectrograms...)
 *
 * @sa DataSeries
 */
#ifndef SCIQLOP_DATASERIESTESTSUTILS_H
#define SCIQLOP_DATASERIESTESTSUTILS_H

#include <Data/DataSeriesIterator.h>
#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
#include <Data/VectorSeries.h>

#include <memory>
#include <QtTest>

/// Underlying data in ArrayData
using DataContainer = std::vector<double>;

Q_DECLARE_METATYPE(std::shared_ptr<ScalarSeries>)
Q_DECLARE_METATYPE(std::shared_ptr<SpectrogramSeries>)
Q_DECLARE_METATYPE(std::shared_ptr<VectorSeries>)

/**
 * Checks that the range of a 1-dim data series contains the expected x-axis data and values data
 * @param first the iterator on the beginning of the range to check
 * @param last the iterator on the end of the range to check
 * @param xData expected x-axis data for the range
 * @param valuesData expected values data for the range
 */
void validateRange(DataSeriesIterator first, DataSeriesIterator last, const DataContainer &xData,
                   const DataContainer &valuesData);

/**
 * Checks that the range of a 2-dim data series contains the expected x-axis data and values data
 * @param first the iterator on the beginning of the range to check
 * @param last the iterator on the end of the range to check
 * @param xData expected x-axis data for the range
 * @param valuesData expected values data for the range
 */
void validateRange(DataSeriesIterator first, DataSeriesIterator last, const DataContainer &xData,
                   const std::vector<DataContainer> &valuesData);

/**
 * Sets the structure of unit tests concerning merge of two data series
 * @tparam DataSeriesType the type of data series to merge
 * @tparam ExpectedValuesType the type of values expected after merge
 * @sa testMerge_t()
 */
template <typename DataSeriesType, typename ExpectedValuesType>
void testMerge_struct() {
    // Data series to merge
    QTest::addColumn<std::shared_ptr<DataSeriesType> >("dataSeries");
    QTest::addColumn<std::shared_ptr<DataSeriesType> >("dataSeries2");

    // Expected values in the first data series after merge
    QTest::addColumn<DataContainer>("expectedXAxisData");
    QTest::addColumn<ExpectedValuesType>("expectedValuesData");
}

/**
 * Unit test concerning merge of two data series
 * @sa testMerge_struct()
 */
template <typename DataSeriesType, typename ExpectedValuesType>
void testMerge_t(){
    // Merges series
    QFETCH(std::shared_ptr<DataSeriesType>, dataSeries);
    QFETCH(std::shared_ptr<DataSeriesType>, dataSeries2);

    dataSeries->merge(dataSeries2.get());

    // Validates results : we check that the merge is valid
    QFETCH(DataContainer, expectedXAxisData);
    QFETCH(ExpectedValuesType, expectedValuesData);

    validateRange(dataSeries->cbegin(), dataSeries->cend(), expectedXAxisData, expectedValuesData);
}

/**
 * Sets the structure of unit tests concerning merge of two data series that are of a different type
 * @tparam SourceType the type of data series with which to make the merge
 * @tparam DestType the type of data series in which to make the merge
 * @sa testMergeDifferentTypes_t()
 */
template <typename SourceType, typename DestType>
void testMergeDifferentTypes_struct()
{
    // Data series to merge
    QTest::addColumn<std::shared_ptr<DestType> >("dest");
    QTest::addColumn<std::shared_ptr<SourceType> >("source");

    // Expected values in the dest data series after merge
    QTest::addColumn<DataContainer>("expectedXAxisData");
    QTest::addColumn<DataContainer>("expectedValuesData");
}

/**
 * Unit test concerning merge of two data series that are of a different type
 * @sa testMergeDifferentTypes_struct()
 */
template <typename SourceType, typename DestType>
void testMergeDifferentTypes_t()
{
    // Merges series
    QFETCH(std::shared_ptr<SourceType>, source);
    QFETCH(std::shared_ptr<DestType>, dest);

    dest->merge(source.get());

    // Validates results : we check that the merge is valid and the data series is sorted on its
    // x-axis data
    QFETCH(DataContainer, expectedXAxisData);
    QFETCH(DataContainer, expectedValuesData);

    validateRange(dest->cbegin(), dest->cend(), expectedXAxisData, expectedValuesData);
}

/**
 * Sets the structure of unit tests concerning getting the min x-axis data of a data series
 * @tparam T the type of data series on which to make the operation
 * @sa testMinXAxisData_t()
 */
template <typename T>
void testMinXAxisData_struct(){
    // Data series to get min data
    QTest::addColumn<std::shared_ptr<T> >("dataSeries");

    // Min data
    QTest::addColumn<double>("min");

    // Expected results
    QTest::addColumn<bool>(
        "expectedOK"); // if true, expects to have a result (i.e. the iterator != end iterator)
    QTest::addColumn<double>(
        "expectedMin"); // Expected value when method doesn't return end iterator
}

/**
 * Unit test concerning getting the min x-axis data of a data series
 * @sa testMinXAxisData_struct()
 */
template <typename T>
void testMinXAxisData_t()
{
    QFETCH(std::shared_ptr<T>, dataSeries);
    QFETCH(double, min);

    QFETCH(bool, expectedOK);
    QFETCH(double, expectedMin);

    auto it = dataSeries->minXAxisData(min);

    QCOMPARE(expectedOK, it != dataSeries->cend());

    // If the method doesn't return a end iterator, checks with expected value
    if (expectedOK) {
        QCOMPARE(expectedMin, it->x());
    }
}

/**
 * Sets the structure of unit tests concerning getting the max x-axis data of a data series
 * @tparam T the type of data series on which to make the operation
 * @sa testMaxXAxisData_t()
 */
template <typename T>
void testMaxXAxisData_struct(){
    // Data series to get max data
    QTest::addColumn<std::shared_ptr<T> >("dataSeries");

    // Max data
    QTest::addColumn<double>("max");

    // Expected results
    QTest::addColumn<bool>(
        "expectedOK"); // if true, expects to have a result (i.e. the iterator != end iterator)
    QTest::addColumn<double>(
        "expectedMax"); // Expected value when method doesn't return end iterator

}

/**
 * Unit test concerning getting the max x-axis data of a data series
 * @sa testMaxXAxisData_struct()
 */
template <typename T>
void testMaxXAxisData_t()
{
    QFETCH(std::shared_ptr<T>, dataSeries);
    QFETCH(double, max);

    QFETCH(bool, expectedOK);
    QFETCH(double, expectedMax);

    auto it = dataSeries->maxXAxisData(max);

    QCOMPARE(expectedOK, it != dataSeries->cend());

    // If the method doesn't return a end iterator, checks with expected value
    if (expectedOK) {
        QCOMPARE(expectedMax, it->x());
    }
}

/**
 * Sets the structure of unit tests concerning getting the purge of a data series
 * @tparam T the type of data series on which to make the operation
 * @sa testMinXAxisData_t()
 */
template <typename T>
void testPurge_struct()
{
    // Data series to purge
    QTest::addColumn<std::shared_ptr<T> >("dataSeries");
    QTest::addColumn<double>("min");
    QTest::addColumn<double>("max");

    // Expected values after purge
    QTest::addColumn<DataContainer>("expectedXAxisData");
    QTest::addColumn<std::vector<DataContainer> >("expectedValuesData");
}

/**
 * Unit test concerning getting the purge of a data series
 * @sa testPurge_struct()
 */
template <typename T>
void testPurge_t(){
    QFETCH(std::shared_ptr<T>, dataSeries);
    QFETCH(double, min);
    QFETCH(double, max);

    dataSeries->purge(min, max);

    // Validates results
    QFETCH(DataContainer, expectedXAxisData);
    QFETCH(std::vector<DataContainer>, expectedValuesData);

    validateRange(dataSeries->cbegin(), dataSeries->cend(), expectedXAxisData,
                  expectedValuesData);
}

/**
 * Sets the structure of unit tests concerning getting subdata of a data series
 * @tparam DataSeriesType the type of data series on which to make the operation
 * @tparam ExpectedValuesType the type of values expected after the operation
 * @sa testSubDataSeries_t()
 */
template <typename DataSeriesType, typename ExpectedValuesType>
void testSubDataSeries_struct() {
    // Data series from which extract the subdata series
    QTest::addColumn<std::shared_ptr<DataSeriesType> >("dataSeries");
    // Range to extract
    QTest::addColumn<DateTimeRange>("range");

    // Expected values for the subdata series
    QTest::addColumn<DataContainer>("expectedXAxisData");
    QTest::addColumn<ExpectedValuesType>("expectedValuesData");
}

/**
 * Unit test concerning getting subdata of a data series
 * @sa testSubDataSeries_struct()
 */
template <typename DataSeriesType, typename ExpectedValuesType>
void testSubDataSeries_t(){
    QFETCH(std::shared_ptr<DataSeriesType>, dataSeries);
    QFETCH(DateTimeRange, range);

    // Makes the operation
    auto subDataSeries = std::dynamic_pointer_cast<DataSeriesType>(dataSeries->subDataSeries(range));
    QVERIFY(subDataSeries != nullptr);

    // Validates results
    QFETCH(DataContainer, expectedXAxisData);
    QFETCH(ExpectedValuesType, expectedValuesData);

    validateRange(subDataSeries->cbegin(), subDataSeries->cend(), expectedXAxisData, expectedValuesData);
}

/**
 * Sets the structure of unit tests concerning getting the range of a data series
 * @tparam T the type of data series on which to make the operation
 * @sa testXAxisRange_t()
 */
template <typename T>
void testXAxisRange_struct(){
    // Data series to get x-axis range
    QTest::addColumn<std::shared_ptr<T> >("dataSeries");

    // Min/max values
    QTest::addColumn<double>("min");
    QTest::addColumn<double>("max");

    // Expected values
    QTest::addColumn<DataContainer>("expectedXAxisData");
    QTest::addColumn<DataContainer>("expectedValuesData");
}

/**
 * Unit test concerning getting the range of a data series
 * @sa testXAxisRange_struct()
 */
template <typename T>
void testXAxisRange_t(){
    QFETCH(std::shared_ptr<T>, dataSeries);
    QFETCH(double, min);
    QFETCH(double, max);

    QFETCH(DataContainer, expectedXAxisData);
    QFETCH(DataContainer, expectedValuesData);

    auto bounds = dataSeries->xAxisRange(min, max);
    validateRange(bounds.first, bounds.second, expectedXAxisData, expectedValuesData);
}

/**
 * Sets the structure of unit tests concerning getting values bounds of a data series
 * @tparam T the type of data series on which to make the operation
 * @sa testValuesBounds_t()
 */
template <typename T>
void testValuesBounds_struct()
{
    // Data series to get values bounds
    QTest::addColumn<std::shared_ptr<T> >("dataSeries");

    // x-axis range
    QTest::addColumn<double>("minXAxis");
    QTest::addColumn<double>("maxXAxis");

    // Expected results
    QTest::addColumn<bool>(
        "expectedOK"); // Test is expected to be ok (i.e. method doesn't return end iterators)
    QTest::addColumn<double>("expectedMinValue");
    QTest::addColumn<double>("expectedMaxValue");
}

/**
 * Unit test concerning getting values bounds of a data series
 * @sa testValuesBounds_struct()
 */
template <typename T>
void testValuesBounds_t()
{
    QFETCH(std::shared_ptr<T>, dataSeries);
    QFETCH(double, minXAxis);
    QFETCH(double, maxXAxis);

    QFETCH(bool, expectedOK);
    QFETCH(double, expectedMinValue);
    QFETCH(double, expectedMaxValue);

    auto minMaxIts = dataSeries->valuesBounds(minXAxis, maxXAxis);
    auto end = dataSeries->cend();

    // Checks iterators with expected result
    QCOMPARE(expectedOK, minMaxIts.first != end && minMaxIts.second != end);

    if (expectedOK) {
        auto compare = [](const auto &v1, const auto &v2) {
            return (std::isnan(v1) && std::isnan(v2)) || v1 == v2;
        };

        QVERIFY(compare(expectedMinValue, minMaxIts.first->minValue()));
        QVERIFY(compare(expectedMaxValue, minMaxIts.second->maxValue()));
    }
}

#endif // SCIQLOP_DATASERIESTESTSUTILS_H
