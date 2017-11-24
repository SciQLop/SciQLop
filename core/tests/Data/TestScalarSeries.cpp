#include "Data/ScalarSeries.h"

#include "DataSeriesBuilders.h"
#include "DataSeriesTestsUtils.h"

#include <QObject>
#include <QtTest>

/**
 * @brief The TestScalarSeries class defines unit tests on scalar series.
 *
 * Most of these unit tests use generic tests defined for DataSeries (@sa DataSeriesTestsUtils)
 */
class TestScalarSeries : public QObject {
    Q_OBJECT
private slots:
    /// Tests construction of a scalar series
    void testCtor_data();
    void testCtor();

    /// Tests merge of two scalar series
    void testMerge_data();
    void testMerge();

    /// Tests merge of a vector series in a scalar series
    void testMergeWithVector_data();
    void testMergeWithVector();

    /// Tests get min x-axis data of a scalar series
    void testMinXAxisData_data();
    void testMinXAxisData();

    /// Tests get max x-axis data of a scalar series
    void testMaxXAxisData_data();
    void testMaxXAxisData();

    /// Tests purge of a scalar series
    void testPurge_data();
    void testPurge();

    /// Tests get x-axis range of a scalar series
    void testXAxisRange_data();
    void testXAxisRange();

    /// Tests get values bounds of a scalar series
    void testValuesBounds_data();
    void testValuesBounds();
};

void TestScalarSeries::testCtor_data()
{
    // x-axis data
    QTest::addColumn<DataContainer>("xAxisData");
    // values data
    QTest::addColumn<DataContainer>("valuesData");

    // construction expected to be valid
    QTest::addColumn<bool>("expectOK");
    // expected x-axis data (when construction is valid)
    QTest::addColumn<DataContainer>("expectedXAxisData");
    // expected values data (when construction is valid)
    QTest::addColumn<DataContainer>("expectedValuesData");

    QTest::newRow("invalidData (different sizes of vectors)")
        << DataContainer{1., 2., 3., 4., 5.} << DataContainer{100., 200., 300.} << false
        << DataContainer{} << DataContainer{};

    QTest::newRow("sortedData") << DataContainer{1., 2., 3., 4., 5.}
                                << DataContainer{100., 200., 300., 400., 500.} << true
                                << DataContainer{1., 2., 3., 4., 5.}
                                << DataContainer{100., 200., 300., 400., 500.};

    QTest::newRow("unsortedData") << DataContainer{5., 4., 3., 2., 1.}
                                  << DataContainer{100., 200., 300., 400., 500.} << true
                                  << DataContainer{1., 2., 3., 4., 5.}
                                  << DataContainer{500., 400., 300., 200., 100.};

    QTest::newRow("unsortedData2")
        << DataContainer{1., 4., 3., 5., 2.} << DataContainer{100., 200., 300., 400., 500.} << true
        << DataContainer{1., 2., 3., 4., 5.} << DataContainer{100., 500., 300., 200., 400.};
}

void TestScalarSeries::testCtor()
{
    // Creates series
    QFETCH(DataContainer, xAxisData);
    QFETCH(DataContainer, valuesData);
    QFETCH(bool, expectOK);

    if (expectOK) {
        auto series = std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData),
                                                     Unit{}, Unit{});

        // Validates results : we check that the data series is sorted on its x-axis data
        QFETCH(DataContainer, expectedXAxisData);
        QFETCH(DataContainer, expectedValuesData);

        validateRange(series->cbegin(), series->cend(), expectedXAxisData, expectedValuesData);
    }
    else {
        QVERIFY_EXCEPTION_THROWN(std::make_shared<ScalarSeries>(
                                     std::move(xAxisData), std::move(valuesData), Unit{}, Unit{}),
                                 std::invalid_argument);
    }
}

void TestScalarSeries::testMerge_data()
{
    testMerge_struct<ScalarSeries, DataContainer>();

    QTest::newRow("sortedMerge") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << ScalarBuilder{}
                                        .setX({6., 7., 8., 9., 10.})
                                        .setValues({600., 700., 800., 900., 1000.})
                                        .build()
                                 << DataContainer{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
                                 << DataContainer{100., 200., 300., 400., 500.,
                                                  600., 700., 800., 900., 1000.};

    QTest::newRow("unsortedMerge")
        << ScalarBuilder{}
               .setX({6., 7., 8., 9., 10.})
               .setValues({600., 700., 800., 900., 1000.})
               .build()
        << ScalarBuilder{}
               .setX({1., 2., 3., 4., 5.})
               .setValues({100., 200., 300., 400., 500.})
               .build()
        << DataContainer{1., 2., 3., 4., 5., 6., 7., 8., 9., 10.}
        << DataContainer{100., 200., 300., 400., 500., 600., 700., 800., 900., 1000.};

    QTest::newRow("unsortedMerge2 (merge not made because source is in the bounds of dest)")
        << ScalarBuilder{}
               .setX({1., 2., 8., 9., 10})
               .setValues({100., 200., 800., 900., 1000.})
               .build()
        << ScalarBuilder{}
               .setX({3., 4., 5., 6., 7.})
               .setValues({300., 400., 500., 600., 700.})
               .build()
        << DataContainer{1., 2., 8., 9., 10.} << DataContainer{100., 200., 800., 900., 1000.};

    QTest::newRow("unsortedMerge3")
        << ScalarBuilder{}
               .setX({3., 4., 5., 7., 8})
               .setValues({300., 400., 500., 700., 800.})
               .build()
        << ScalarBuilder{}
               .setX({1., 2., 3., 7., 10.})
               .setValues({100., 200., 333., 777., 1000.})
               .build()
        << DataContainer{1., 2., 3., 4., 5., 7., 8., 10.}
        << DataContainer{100., 200., 300., 400., 500., 700., 800., 1000.};

    QTest::newRow("emptySource") << ScalarBuilder{}
                                        .setX({3., 4., 5., 7., 8})
                                        .setValues({300., 400., 500., 700., 800.})
                                        .build()
                                 << ScalarBuilder{}.setX({}).setValues({}).build()
                                 << DataContainer{3., 4., 5., 7., 8.}
                                 << DataContainer{300., 400., 500., 700., 800.};
}

void TestScalarSeries::testMerge()
{
    testMerge_t<ScalarSeries, DataContainer>();
}

void TestScalarSeries::testMergeWithVector_data()
{
    testMergeDifferentTypes_struct<VectorSeries, ScalarSeries>();

    QTest::newRow("mergeVectorInScalar") << ScalarBuilder{}
                                                .setX({1., 2., 3., 4., 5.})
                                                .setValues({100., 200., 300., 400., 500.})
                                                .build()
                                         << VectorBuilder{}
                                                .setX({6., 7., 8., 9., 10.})
                                                .setXValues({600., 700., 800., 900., 1000.})
                                                .setYValues({610., 710., 810., 910., 1010.})
                                                .setZValues({620., 720., 820., 920., 1020.})
                                                .build()
                                         << DataContainer{1., 2., 3., 4., 5.}
                                         << DataContainer{100., 200., 300., 400., 500.};
}

void TestScalarSeries::testMergeWithVector()
{
    testMergeDifferentTypes_t<VectorSeries, ScalarSeries>();
}

void TestScalarSeries::testMinXAxisData_data()
{
    testMinXAxisData_struct<ScalarSeries>();

    QTest::newRow("minData1") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 0. << true << 1.;
    QTest::newRow("minData2") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 1. << true << 1.;
    QTest::newRow("minData3") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 1.1 << true << 2.;
    QTest::newRow("minData4") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 5. << true << 5.;
    QTest::newRow("minData5") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 5.1 << false << std::numeric_limits<double>::quiet_NaN();
    QTest::newRow("minData6") << ScalarBuilder{}.setX({}).setValues({}).build() << 1.1 << false
                              << std::numeric_limits<double>::quiet_NaN();
}

void TestScalarSeries::testMinXAxisData()
{
    testMinXAxisData_t<ScalarSeries>();
}

void TestScalarSeries::testMaxXAxisData_data()
{
    testMaxXAxisData_struct<ScalarSeries>();

    QTest::newRow("maxData1") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 6. << true << 5.;
    QTest::newRow("maxData2") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 5. << true << 5.;
    QTest::newRow("maxData3") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 4.9 << true << 4.;
    QTest::newRow("maxData4") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 1.1 << true << 1.;
    QTest::newRow("maxData5") << ScalarBuilder{}
                                     .setX({1., 2., 3., 4., 5.})
                                     .setValues({100., 200., 300., 400., 500.})
                                     .build()
                              << 1. << true << 1.;
    QTest::newRow("maxData6") << ScalarBuilder{}.setX({}).setValues({}).build() << 1.1 << false
                              << std::numeric_limits<double>::quiet_NaN();
}

void TestScalarSeries::testMaxXAxisData()
{
    testMaxXAxisData_t<ScalarSeries>();
}

void TestScalarSeries::testPurge_data()
{
    testPurge_struct<ScalarSeries>();

    QTest::newRow("purgeScalar") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 2. << 4. << DataContainer{2., 3., 4.}
                                 << std::vector<DataContainer>{{200., 300., 400.}};
    QTest::newRow("purgeScalar1 (min/max swap)") << ScalarBuilder{}
                                                        .setX({1., 2., 3., 4., 5.})
                                                        .setValues({100., 200., 300., 400., 500.})
                                                        .build()
                                                 << 4. << 2. << DataContainer{2., 3., 4.}
                                                 << std::vector<DataContainer>{{200., 300., 400.}};
    QTest::newRow("purgeScalar2") << ScalarBuilder{}
                                         .setX({1., 2., 3., 4., 5.})
                                         .setValues({100., 200., 300., 400., 500.})
                                         .build()
                                  << 0. << 2.5 << DataContainer{1., 2.}
                                  << std::vector<DataContainer>{{100., 200.}};
    QTest::newRow("purgeScalar3") << ScalarBuilder{}
                                         .setX({1., 2., 3., 4., 5.})
                                         .setValues({100., 200., 300., 400., 500.})
                                         .build()
                                  << 3.5 << 7. << DataContainer{4., 5.}
                                  << std::vector<DataContainer>{{400., 500.}};
    QTest::newRow("purgeScalar4") << ScalarBuilder{}
                                         .setX({1., 2., 3., 4., 5.})
                                         .setValues({100., 200., 300., 400., 500.})
                                         .build()
                                  << 0. << 7. << DataContainer{1., 2., 3., 4., 5.}
                                  << std::vector<DataContainer>{{100., 200., 300., 400., 500.}};
    QTest::newRow("purgeScalar5") << ScalarBuilder{}
                                         .setX({1., 2., 3., 4., 5.})
                                         .setValues({100., 200., 300., 400., 500.})
                                         .build()
                                  << 5.5 << 7. << DataContainer{} << std::vector<DataContainer>{{}};
}

void TestScalarSeries::testPurge()
{
    testPurge_t<ScalarSeries>();
}

void TestScalarSeries::testXAxisRange_data()
{
    testXAxisRange_struct<ScalarSeries>();

    QTest::newRow("xAxisRange") << ScalarBuilder{}
                                       .setX({1., 2., 3., 4., 5.})
                                       .setValues({100., 200., 300., 400., 500.})
                                       .build()
                                << -1. << 3.2 << DataContainer{1., 2., 3.}
                                << DataContainer{100., 200., 300.};
    QTest::newRow("xAxisRange1 (min/max swap)") << ScalarBuilder{}
                                                       .setX({1., 2., 3., 4., 5.})
                                                       .setValues({100., 200., 300., 400., 500.})
                                                       .build()
                                                << 3.2 << -1. << DataContainer{1., 2., 3.}
                                                << DataContainer{100., 200., 300.};
    QTest::newRow("xAxisRange2") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 1. << 4. << DataContainer{1., 2., 3., 4.}
                                 << DataContainer{100., 200., 300., 400.};
    QTest::newRow("xAxisRange3") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 1. << 3.9 << DataContainer{1., 2., 3.}
                                 << DataContainer{100., 200., 300.};
    QTest::newRow("xAxisRange4") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 0. << 0.9 << DataContainer{} << DataContainer{};
    QTest::newRow("xAxisRange5") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 0. << 1. << DataContainer{1.} << DataContainer{100.};
    QTest::newRow("xAxisRange6") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 2.1 << 6. << DataContainer{3., 4., 5.}
                                 << DataContainer{300., 400., 500.};
    QTest::newRow("xAxisRange7") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 6. << 9. << DataContainer{} << DataContainer{};
    QTest::newRow("xAxisRange8") << ScalarBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setValues({100., 200., 300., 400., 500.})
                                        .build()
                                 << 5. << 9. << DataContainer{5.} << DataContainer{500.};
}

void TestScalarSeries::testXAxisRange()
{
    testXAxisRange_t<ScalarSeries>();
}

void TestScalarSeries::testValuesBounds_data()
{
    testValuesBounds_struct<ScalarSeries>();

    auto nan = std::numeric_limits<double>::quiet_NaN();

    QTest::newRow("scalarBounds1") << ScalarBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setValues({100., 200., 300., 400., 500.})
                                          .build()
                                   << 0. << 6. << true << 100. << 500.;
    QTest::newRow("scalarBounds2") << ScalarBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setValues({100., 200., 300., 400., 500.})
                                          .build()
                                   << 2. << 4. << true << 200. << 400.;
    QTest::newRow("scalarBounds3") << ScalarBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setValues({100., 200., 300., 400., 500.})
                                          .build()
                                   << 0. << 0.5 << false << nan << nan;
    QTest::newRow("scalarBounds4") << ScalarBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setValues({100., 200., 300., 400., 500.})
                                          .build()
                                   << 5.1 << 6. << false << nan << nan;
    QTest::newRow("scalarBounds5") << ScalarBuilder{}.setX({1.}).setValues({100.}).build() << 0.
                                   << 2. << true << 100. << 100.;
    QTest::newRow("scalarBounds6") << ScalarBuilder{}.setX({}).setValues({}).build() << 0. << 2.
                                   << false << nan << nan;

    // Tests with NaN values: NaN values are not included in min/max search
    QTest::newRow("scalarBounds7") << ScalarBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setValues({nan, 200., 300., 400., nan})
                                          .build()
                                   << 0. << 6. << true << 200. << 400.;
    QTest::newRow("scalarBounds8")
        << ScalarBuilder{}.setX({1., 2., 3., 4., 5.}).setValues({nan, nan, nan, nan, nan}).build()
        << 0. << 6. << true << nan << nan;
}

void TestScalarSeries::testValuesBounds()
{
    testValuesBounds_t<ScalarSeries>();
}

QTEST_MAIN(TestScalarSeries)
#include "TestScalarSeries.moc"
