#include "Data/VectorSeries.h"

#include "DataSeriesBuilders.h"
#include "DataSeriesTestsUtils.h"

#include <QObject>
#include <QtTest>

/**
 * @brief The TestVectorSeries class defines unit tests on vector series.
 *
 * Most of these unit tests use generic tests defined for DataSeries (@sa DataSeriesTestsUtils)
 */
class TestVectorSeries : public QObject {
    Q_OBJECT
private slots:
    /// Tests purge of a vector series
    void testPurge_data();
    void testPurge();

    /// Tests get values bounds of a vector series
    void testValuesBounds_data();
    void testValuesBounds();
};

void TestVectorSeries::testPurge_data()
{
    testPurge_struct<VectorSeries>();

    QTest::newRow("purgeVector") << VectorBuilder{}
                                        .setX({1., 2., 3., 4., 5.})
                                        .setXValues({6., 7., 8., 9., 10.})
                                        .setYValues({11., 12., 13., 14., 15.})
                                        .setZValues({16., 17., 18., 19., 20.})
                                        .build()
                                 << 2. << 4. << DataContainer{2., 3., 4.}
                                 << std::vector<DataContainer>{
                                        {7., 8., 9.}, {12., 13., 14.}, {17., 18., 19.}};
}

void TestVectorSeries::testPurge()
{
    testPurge_t<VectorSeries>();
}

void TestVectorSeries::testValuesBounds_data()
{
    testValuesBounds_struct<VectorSeries>();

    auto nan = std::numeric_limits<double>::quiet_NaN();

    QTest::newRow("vectorBounds1") << VectorBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setXValues({10., 15., 20., 13., 12.})
                                          .setYValues({35., 24., 10., 9., 0.3})
                                          .setZValues({13., 14., 12., 9., 24.})
                                          .build()
                                   << 0. << 6. << true << 0.3 << 35.; // min/max in same component
    QTest::newRow("vectorBounds2") << VectorBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setXValues({2.3, 15., 20., 13., 12.})
                                          .setYValues({35., 24., 10., 9., 4.})
                                          .setZValues({13., 14., 12., 9., 24.})
                                          .build()
                                   << 0. << 6. << true << 2.3 << 35.; // min/max in same entry
    QTest::newRow("vectorBounds3") << VectorBuilder{}
                                          .setX({1., 2., 3., 4., 5.})
                                          .setXValues({2.3, 15., 20., 13., 12.})
                                          .setYValues({35., 24., 10., 9., 4.})
                                          .setZValues({13., 14., 12., 9., 24.})
                                          .build()
                                   << 2. << 3. << true << 10. << 24.;

    // Tests with NaN values: NaN values are not included in min/max search
    QTest::newRow("vectorBounds4") << VectorBuilder{}
                                          .setX({1., 2.})
                                          .setXValues({nan, nan})
                                          .setYValues({nan, nan})
                                          .setZValues({nan, nan})
                                          .build()
                                   << 0. << 6. << true << nan << nan;
}

void TestVectorSeries::testValuesBounds()
{
    testValuesBounds_t<VectorSeries>();
}

QTEST_MAIN(TestVectorSeries)
#include "TestVectorSeries.moc"
