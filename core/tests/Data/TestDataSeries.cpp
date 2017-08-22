#include "Data/DataSeries.h"
#include "Data/ScalarSeries.h"
#include "Data/VectorSeries.h"

#include <QObject>
#include <QtTest>

Q_DECLARE_METATYPE(std::shared_ptr<ScalarSeries>)
Q_DECLARE_METATYPE(std::shared_ptr<VectorSeries>)

class TestDataSeries : public QObject {
    Q_OBJECT
private:
    template <typename T>
    void testValuesBoundsStructure()
    {
        // ////////////// //
        // Test structure //
        // ////////////// //

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

    template <typename T>
    void testValuesBounds()
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

private slots:
    /// Input test data
    /// @sa testCtor()
    void testCtor_data();

    /// Tests construction of a data series
    void testCtor();

    /// Input test data
    /// @sa testMerge()
    void testMerge_data();

    /// Tests merge of two data series
    void testMerge();

    /// Input test data
    /// @sa testMinXAxisData()
    void testMinXAxisData_data();

    /// Tests get min x-axis data of a data series
    void testMinXAxisData();

    /// Input test data
    /// @sa testMaxXAxisData()
    void testMaxXAxisData_data();

    /// Tests get max x-axis data of a data series
    void testMaxXAxisData();

    /// Input test data
    /// @sa testXAxisRange()
    void testXAxisRange_data();

    /// Tests get x-axis range of a data series
    void testXAxisRange();

    /// Input test data
    /// @sa testValuesBoundsScalar()
    void testValuesBoundsScalar_data();

    /// Tests get values bounds of a scalar series
    void testValuesBoundsScalar();
};

void TestDataSeries::testCtor_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // x-axis data
    QTest::addColumn<QVector<double> >("xAxisData");
    // values data
    QTest::addColumn<QVector<double> >("valuesData");

    // expected x-axis data
    QTest::addColumn<QVector<double> >("expectedXAxisData");
    // expected values data
    QTest::addColumn<QVector<double> >("expectedValuesData");

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("invalidData (different sizes of vectors)")
        << QVector<double>{1., 2., 3., 4., 5.} << QVector<double>{100., 200., 300.}
        << QVector<double>{} << QVector<double>{};

    QTest::newRow("sortedData") << QVector<double>{1., 2., 3., 4., 5.}
                                << QVector<double>{100., 200., 300., 400., 500.}
                                << QVector<double>{1., 2., 3., 4., 5.}
                                << QVector<double>{100., 200., 300., 400., 500.};

    QTest::newRow("unsortedData") << QVector<double>{5., 4., 3., 2., 1.}
                                  << QVector<double>{100., 200., 300., 400., 500.}
                                  << QVector<double>{1., 2., 3., 4., 5.}
                                  << QVector<double>{500., 400., 300., 200., 100.};

    QTest::newRow("unsortedData2")
        << QVector<double>{1., 4., 3., 5., 2.} << QVector<double>{100., 200., 300., 400., 500.}
        << QVector<double>{1., 2., 3., 4., 5.} << QVector<double>{100., 500., 300., 200., 400.};
}

void TestDataSeries::testCtor()
{
    // Creates series
    QFETCH(QVector<double>, xAxisData);
    QFETCH(QVector<double>, valuesData);

    auto series = std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData),
                                                 Unit{}, Unit{});

    // Validates results : we check that the data series is sorted on its x-axis data
    QFETCH(QVector<double>, expectedXAxisData);
    QFETCH(QVector<double>, expectedValuesData);

    auto seriesXAxisData = series->xAxisData()->data();
    auto seriesValuesData = series->valuesData()->data();

    QVERIFY(
        std::equal(expectedXAxisData.cbegin(), expectedXAxisData.cend(), seriesXAxisData.cbegin()));
    QVERIFY(std::equal(expectedValuesData.cbegin(), expectedValuesData.cend(),
                       seriesValuesData.cbegin()));
}

namespace {

std::shared_ptr<ScalarSeries> createSeries(QVector<double> xAxisData, QVector<double> valuesData)
{
    return std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData), Unit{},
                                          Unit{});
}

} // namespace

void TestDataSeries::testMerge_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Data series to merge
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries2");

    // Expected values in the first data series after merge
    QTest::addColumn<QVector<double> >("expectedXAxisData");
    QTest::addColumn<QVector<double> >("expectedValuesData");

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("sortedMerge")
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
        << createSeries({6., 7., 8., 9., 10.}, {600., 700., 800., 900., 1000.})
        << QVector<double>{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
        << QVector<double>{100., 200., 300., 400., 500., 600., 700., 800., 900., 1000.};

    QTest::newRow("unsortedMerge")
        << createSeries({6., 7., 8., 9., 10.}, {600., 700., 800., 900., 1000.})
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
        << QVector<double>{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
        << QVector<double>{100., 200., 300., 400., 500., 600., 700., 800., 900., 1000.};

    QTest::newRow("unsortedMerge2")
        << createSeries({1., 2., 8., 9., 10}, {100., 200., 300., 400., 500.})
        << createSeries({3., 4., 5., 6., 7.}, {600., 700., 800., 900., 1000.})
        << QVector<double>{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
        << QVector<double>{100., 200., 600., 700., 800., 900., 1000., 300., 400., 500.};

    QTest::newRow("unsortedMerge3")
        << createSeries({3., 5., 8., 7., 2}, {100., 200., 300., 400., 500.})
        << createSeries({6., 4., 9., 10., 1.}, {600., 700., 800., 900., 1000.})
        << QVector<double>{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
        << QVector<double>{1000., 500., 100., 700., 200., 600., 400., 300., 800., 900.};
}

void TestDataSeries::testMerge()
{
    // Merges series
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries);
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries2);

    dataSeries->merge(dataSeries2.get());

    // Validates results : we check that the merge is valid and the data series is sorted on its
    // x-axis data
    QFETCH(QVector<double>, expectedXAxisData);
    QFETCH(QVector<double>, expectedValuesData);

    auto seriesXAxisData = dataSeries->xAxisData()->data();
    auto seriesValuesData = dataSeries->valuesData()->data();

    QVERIFY(
        std::equal(expectedXAxisData.cbegin(), expectedXAxisData.cend(), seriesXAxisData.cbegin()));
    QVERIFY(std::equal(expectedValuesData.cbegin(), expectedValuesData.cend(),
                       seriesValuesData.cbegin()));
}

void TestDataSeries::testMinXAxisData_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Data series to get min data
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");

    // Min data
    QTest::addColumn<double>("min");

    // Expected results
    QTest::addColumn<bool>(
        "expectedOK"); // if true, expects to have a result (i.e. the iterator != end iterator)
    QTest::addColumn<double>(
        "expectedMin"); // Expected value when method doesn't return end iterator

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("minData1") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 0. << true << 1.;
    QTest::newRow("minData2") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 1. << true << 1.;
    QTest::newRow("minData3") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 1.1 << true << 2.;
    QTest::newRow("minData4") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 5. << true << 5.;
    QTest::newRow("minData5") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 5.1 << false << std::numeric_limits<double>::quiet_NaN();
    QTest::newRow("minData6") << createSeries({}, {}) << 1.1 << false
                              << std::numeric_limits<double>::quiet_NaN();
}

void TestDataSeries::testMinXAxisData()
{
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries);
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

void TestDataSeries::testMaxXAxisData_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Data series to get max data
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");

    // Max data
    QTest::addColumn<double>("max");

    // Expected results
    QTest::addColumn<bool>(
        "expectedOK"); // if true, expects to have a result (i.e. the iterator != end iterator)
    QTest::addColumn<double>(
        "expectedMax"); // Expected value when method doesn't return end iterator

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("maxData1") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 6. << true << 5.;
    QTest::newRow("maxData2") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 5. << true << 5.;
    QTest::newRow("maxData3") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 4.9 << true << 4.;
    QTest::newRow("maxData4") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 1.1 << true << 1.;
    QTest::newRow("maxData5") << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.})
                              << 1. << true << 1.;
    QTest::newRow("maxData6") << createSeries({}, {}) << 1.1 << false
                              << std::numeric_limits<double>::quiet_NaN();
}

void TestDataSeries::testMaxXAxisData()
{
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries);
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

void TestDataSeries::testXAxisRange_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Data series to get x-axis range
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");

    // Min/max values
    QTest::addColumn<double>("min");
    QTest::addColumn<double>("max");

    // Expected values
    QTest::addColumn<QVector<double> >("expectedXAxisData");
    QTest::addColumn<QVector<double> >("expectedValuesData");

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("xAxisRange1") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << -1. << 3.2 << QVector<double>{1., 2., 3.}
                                 << QVector<double>{100., 200., 300.};
    QTest::newRow("xAxisRange2") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 1. << 4. << QVector<double>{1., 2., 3., 4.}
                                 << QVector<double>{100., 200., 300., 400.};
    QTest::newRow("xAxisRange3") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 1. << 3.9 << QVector<double>{1., 2., 3.}
                                 << QVector<double>{100., 200., 300.};
    QTest::newRow("xAxisRange4") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 0. << 0.9 << QVector<double>{} << QVector<double>{};
    QTest::newRow("xAxisRange5") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 0. << 1. << QVector<double>{1.} << QVector<double>{100.};
    QTest::newRow("xAxisRange6") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 2.1 << 6. << QVector<double>{3., 4., 5.}
                                 << QVector<double>{300., 400., 500.};
    QTest::newRow("xAxisRange7") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 6. << 9. << QVector<double>{} << QVector<double>{};
    QTest::newRow("xAxisRange8") << createSeries({1., 2., 3., 4., 5.},
                                                 {100., 200., 300., 400., 500.})
                                 << 5. << 9. << QVector<double>{5.} << QVector<double>{500.};
}

void TestDataSeries::testXAxisRange()
{
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries);
    QFETCH(double, min);
    QFETCH(double, max);

    QFETCH(QVector<double>, expectedXAxisData);
    QFETCH(QVector<double>, expectedValuesData);

    auto bounds = dataSeries->xAxisRange(min, max);
    QVERIFY(std::equal(bounds.first, bounds.second, expectedXAxisData.cbegin(),
                       expectedXAxisData.cend(),
                       [](const auto &it, const auto &expectedX) { return it.x() == expectedX; }));
    QVERIFY(std::equal(
        bounds.first, bounds.second, expectedValuesData.cbegin(), expectedValuesData.cend(),
        [](const auto &it, const auto &expectedVal) { return it.value() == expectedVal; }));
}

void TestDataSeries::testValuesBoundsScalar_data()
{
    testValuesBoundsStructure<ScalarSeries>();

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("valuesBounds1")
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.}) << 0. << 6. << true
        << 100. << 500.;
    QTest::newRow("valuesBounds2")
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.}) << 2. << 4. << true
        << 200. << 400.;
    QTest::newRow("valuesBounds3")
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.}) << 0. << 0.5 << false
        << std::numeric_limits<double>::quiet_NaN() << std::numeric_limits<double>::quiet_NaN();
    QTest::newRow("valuesBounds4")
        << createSeries({1., 2., 3., 4., 5.}, {100., 200., 300., 400., 500.}) << 5.1 << 6. << false
        << std::numeric_limits<double>::quiet_NaN() << std::numeric_limits<double>::quiet_NaN();
    QTest::newRow("valuesBounds5")
        << createSeries({1.}, {100.}) << 0. << 2. << true << 100. << 100.;
    QTest::newRow("valuesBounds6")
        << createSeries({}, {}) << 0. << 2. << false << std::numeric_limits<double>::quiet_NaN()
        << std::numeric_limits<double>::quiet_NaN();

    // Tests with NaN values: NaN values are not included in min/max search
    QTest::newRow("valuesBounds7")
        << createSeries({1., 2., 3., 4., 5.},
                        {std::numeric_limits<double>::quiet_NaN(), 200., 300., 400.,
                         std::numeric_limits<double>::quiet_NaN()})
        << 0. << 6. << true << 200. << 400.;
    QTest::newRow("valuesBounds8")
        << createSeries(
               {1., 2., 3., 4., 5.},
               {std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN(),
                std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::quiet_NaN(),
                std::numeric_limits<double>::quiet_NaN()})
        << 0. << 6. << true << std::numeric_limits<double>::quiet_NaN()
        << std::numeric_limits<double>::quiet_NaN();
}

void TestDataSeries::testValuesBoundsScalar()
{
    testValuesBounds<ScalarSeries>();
}

QTEST_MAIN(TestDataSeries)
#include "TestDataSeries.moc"
