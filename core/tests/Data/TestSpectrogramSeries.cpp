#include "Data/SpectrogramSeries.h"

#include "DataSeriesBuilders.h"
#include "DataSeriesTestsUtils.h"

#include <QObject>
#include <QtTest>

namespace {

// Aliases used to facilitate reading of test inputs
using X = DataContainer;
using Y = DataContainer;
using Values = DataContainer;
using Components = std::vector<DataContainer>;

} // namespace

/**
 * @brief The TestSpectrogramSeries class defines unit tests on spectrogram series.
 *
 * Most of these unit tests use generic tests defined for DataSeries (@sa DataSeriesTestsUtils)
 */
class TestSpectrogramSeries : public QObject {
    Q_OBJECT
private slots:

    /// Tests construction of a spectrogram series
    void testCtor_data();
    void testCtor();

    /// Tests merge of two spectrogram series
    void testMerge_data();
    void testMerge();

    /// Tests get subdata of a spectrogram series
    void testSubDataSeries_data();
    void testSubDataSeries();
};

void TestSpectrogramSeries::testCtor_data()
{
    // x-axis data
    QTest::addColumn<X>("xAxisData");
    // y-axis data
    QTest::addColumn<Y>("yAxisData");
    // values data
    QTest::addColumn<Values>("valuesData");

    // construction expected to be valid
    QTest::addColumn<bool>("expectOK");
    // expected x-axis data (when construction is valid)
    QTest::addColumn<X>("expectedXAxisData");
    // expected components data (when construction is valid)
    QTest::addColumn<Components>("expectedComponentsData");

    QTest::newRow(
        "invalidData (number of values by component aren't equal to the number of x-axis data)")
        << X{1., 2., 3., 4., 5.} << Y{1., 2., 3.} << Values{1., 2., 3.} << false << X{}
        << Components{};

    QTest::newRow("invalidData (number of components aren't equal to the number of y-axis data)")
        << X{1., 2., 3., 4., 5.} << Y{1., 2.} // 2 y-axis data
        << Values{1., 2., 3., 4., 5.}         // 1 component
        << false << X{} << Components{};

    QTest::newRow("sortedData") << X{1., 2., 3., 4., 5.} << Y{1., 2.}              // 2 y-axis data
                                << Values{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.} // 2 components
                                << true << X{1., 2., 3., 4., 5.}
                                << Components{{1., 3., 5., 7., 9.}, {2., 4., 6., 8., 10.}};

    QTest::newRow("unsortedData") << X{5., 4., 3., 2., 1.} << Y{1., 2.}
                                  << Values{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.} << true
                                  << X{1., 2., 3., 4., 5.}
                                  << Components{{9., 7., 5., 3., 1.}, {10., 8., 6., 4., 2.}};
}

void TestSpectrogramSeries::testCtor()
{
    // Creates series
    QFETCH(X, xAxisData);
    QFETCH(Y, yAxisData);
    QFETCH(Values, valuesData);
    QFETCH(bool, expectOK);

    if (expectOK) {
        auto series = SpectrogramBuilder{}
                          .setX(std::move(xAxisData))
                          .setY(std::move(yAxisData))
                          .setValues(std::move(valuesData))
                          .build();

        // Validates results
        QFETCH(X, expectedXAxisData);
        QFETCH(Components, expectedComponentsData);
        validateRange(series->cbegin(), series->cend(), expectedXAxisData, expectedComponentsData);
    }
    else {
        QVERIFY_EXCEPTION_THROWN(SpectrogramBuilder{}
                                     .setX(std::move(xAxisData))
                                     .setY(std::move(yAxisData))
                                     .setValues(std::move(valuesData))
                                     .build(),
                                 std::invalid_argument);
    }
}

void TestSpectrogramSeries::testMerge_data()
{
    testMerge_struct<SpectrogramSeries, Components>();

    QTest::newRow("sortedMerge") << SpectrogramBuilder{}
                                        .setX({1., 2., 3.})
                                        .setY({1., 2.})
                                        .setValues({10., 11., 20., 21., 30., 31})
                                        .build()
                                 << SpectrogramBuilder{}
                                        .setX({4., 5., 6.})
                                        .setY({1., 2.})
                                        .setValues({40., 41., 50., 51., 60., 61})
                                        .build()
                                 << DataContainer{1., 2., 3., 4., 5., 6.}
                                 << Components{{10., 20., 30., 40., 50., 60.},
                                               {11., 21., 31., 41., 51., 61}};

    QTest::newRow(
        "unsortedMerge (merge not made because the two data series have different y-axes)")
        << SpectrogramBuilder{}
               .setX({4., 5., 6.})
               .setY({1., 2.})
               .setValues({40., 41., 50., 51., 60., 61})
               .build()
        << SpectrogramBuilder{}
               .setX({1., 2., 3.})
               .setY({3., 4.})
               .setValues({10., 11., 20., 21., 30., 31})
               .build()
        << DataContainer{4., 5., 6.} << Components{{40., 50., 60.}, {41., 51., 61}};

    QTest::newRow(
        "unsortedMerge (unsortedMerge (merge is made because the two data series have the same "
        "y-axis)")
        << SpectrogramBuilder{}
               .setX({4., 5., 6.})
               .setY({1., 2.})
               .setValues({40., 41., 50., 51., 60., 61})
               .build()
        << SpectrogramBuilder{}
               .setX({1., 2., 3.})
               .setY({1., 2.})
               .setValues({10., 11., 20., 21., 30., 31})
               .build()
        << DataContainer{1., 2., 3., 4., 5., 6.}
        << Components{{10., 20., 30., 40., 50., 60.}, {11., 21., 31., 41., 51., 61}};
}

void TestSpectrogramSeries::testMerge()
{
    testMerge_t<SpectrogramSeries, Components>();
}

void TestSpectrogramSeries::testSubDataSeries_data()
{
    testSubDataSeries_struct<SpectrogramSeries, Components>();

    QTest::newRow("subDataSeries (the range includes all data)")
        << SpectrogramBuilder{}
               .setX({1., 2., 3.})
               .setY({1., 2.})
               .setValues({10., 11., 20., 21., 30., 31})
               .build()
        << DateTimeRange{0., 5.} << DataContainer{1., 2., 3.}
        << Components{{10., 20., 30.}, {11., 21., 31.}};

    QTest::newRow("subDataSeries (the range includes no data)")
        << SpectrogramBuilder{}
               .setX({1., 2., 3.})
               .setY({1., 2.})
               .setValues({10., 11., 20., 21., 30., 31})
               .build()
        << DateTimeRange{4., 5.} << DataContainer{} << Components{{}, {}};

    QTest::newRow("subDataSeries (the range includes some data)")
        << SpectrogramBuilder{}
               .setX({1., 2., 3.})
               .setY({1., 2.})
               .setValues({10., 11., 20., 21., 30., 31})
               .build()
        << DateTimeRange{1.1, 3} << DataContainer{2., 3.} << Components{{20., 30.}, {21., 31.}};
}

void TestSpectrogramSeries::testSubDataSeries()
{
    testSubDataSeries_t<SpectrogramSeries, Components>();
}

QTEST_MAIN(TestSpectrogramSeries)
#include "TestSpectrogramSeries.moc"
