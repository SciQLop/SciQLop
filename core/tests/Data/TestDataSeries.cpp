#include "Data/DataSeries.h"
#include "Data/ScalarSeries.h"

#include <QObject>
#include <QtTest>

Q_DECLARE_METATYPE(std::shared_ptr<ScalarSeries>)

class TestDataSeries : public QObject {
    Q_OBJECT
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

QTEST_MAIN(TestDataSeries)
#include "TestDataSeries.moc"
