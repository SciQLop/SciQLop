#include <Data/DataSeriesUtils.h>

#include <QObject>
#include <QtTest>

class TestDataSeriesUtils : public QObject {
    Q_OBJECT

private slots:
    /// Tests @sa DataSeriesUtils::fillDataHoles() method
    void testFillDataHoles_data();
    void testFillDataHoles();
};

void TestDataSeriesUtils::testFillDataHoles_data()
{
    QTest::addColumn<std::vector<double> >("xAxisData");
    QTest::addColumn<std::vector<double> >("valuesData");
    QTest::addColumn<double>("resolution");
    QTest::addColumn<double>("fillValue");
    QTest::addColumn<double>("minBound");
    QTest::addColumn<double>("maxBound");
    QTest::addColumn<std::vector<double> >(
        "expectedXAxisData"); // expected x-axis data after filling holes
    QTest::addColumn<std::vector<double> >(
        "expectedValuesData"); // expected values data after filling holes

    auto nan = std::numeric_limits<double>::quiet_NaN();

    QTest::newRow("fillDataHoles (basic case)")
        << std::vector<double>{0., 1., 5., 7., 14.} << std::vector<double>{0., 1., 2., 3., 4.} << 2.
        << nan << nan << nan << std::vector<double>{0., 1., 3., 5., 7., 9., 11., 13., 14.}
        << std::vector<double>{0., 1., nan, 2., 3., nan, nan, nan, 4.};

    QTest::newRow("fillDataHoles (change nb components)")
        << std::vector<double>{0., 1., 5., 7., 14.}
        << std::vector<double>{0., 1., 2., 3., 4., 5., 6., 7., 8., 9.} << 2. << nan << nan << nan
        << std::vector<double>{0., 1., 3., 5., 7., 9., 11., 13., 14.}
        << std::vector<double>{0., 1.,  2.,  3.,  nan, nan, 4.,  5., 6.,
                               7., nan, nan, nan, nan, nan, nan, 8., 9.};

    QTest::newRow("fillDataHoles (change resolution)")
        << std::vector<double>{0., 1., 5., 7., 14.} << std::vector<double>{0., 1., 2., 3., 4.}
        << 1.5 << nan << nan << nan
        << std::vector<double>{0., 1., 2.5, 4., 5., 6.5, 7., 8.5, 10., 11.5, 13., 14.}
        << std::vector<double>{0., 1., nan, nan, 2., nan, 3., nan, nan, nan, nan, 4.};

    QTest::newRow("fillDataHoles (with no data (no changes made))")
        << std::vector<double>{} << std::vector<double>{} << 2. << nan << nan << nan
        << std::vector<double>{} << std::vector<double>{};

    QTest::newRow("fillDataHoles (with no resolution (no changes made))")
        << std::vector<double>{0., 1., 5., 7., 14.} << std::vector<double>{0., 1., 2., 3., 4.} << 0.
        << nan << nan << nan << std::vector<double>{0., 1., 5., 7., 14.}
        << std::vector<double>{0., 1., 2., 3., 4.};

    QTest::newRow("fillDataHoles (change fill value)")
        << std::vector<double>{0., 1., 5., 7., 14.} << std::vector<double>{0., 1., 2., 3., 4.} << 2.
        << -1. << nan << nan << std::vector<double>{0., 1., 3., 5., 7., 9., 11., 13., 14.}
        << std::vector<double>{0., 1., -1., 2., 3., -1., -1., -1., 4.};

    QTest::newRow("fillDataHoles (add data holes to the beginning)")
        << std::vector<double>{5., 7., 9., 11., 13.} << std::vector<double>{0., 1., 2., 3., 4.}
        << 2. << nan << 0. << nan << std::vector<double>{1., 3., 5., 7., 9., 11., 13.}
        << std::vector<double>{nan, nan, 0., 1., 2., 3., 4.};

    QTest::newRow("fillDataHoles (add data holes to the end)")
        << std::vector<double>{5., 7., 9., 11., 13.} << std::vector<double>{0., 1., 2., 3., 4.}
        << 2. << nan << nan << 21. << std::vector<double>{5., 7., 9., 11., 13., 15., 17., 19., 21.}
        << std::vector<double>{0., 1., 2., 3., 4., nan, nan, nan, nan};

    QTest::newRow("fillDataHoles (invalid min/max bounds (no changes made))")
        << std::vector<double>{5., 7., 9., 11., 13.} << std::vector<double>{0., 1., 2., 3., 4.}
        << 2. << nan << 8. << 13. << std::vector<double>{5., 7., 9., 11., 13.}
        << std::vector<double>{0., 1., 2., 3., 4.};
}

void TestDataSeriesUtils::testFillDataHoles()
{
    QFETCH(std::vector<double>, xAxisData);
    QFETCH(std::vector<double>, valuesData);
    QFETCH(double, resolution);
    QFETCH(double, fillValue);
    QFETCH(double, minBound);
    QFETCH(double, maxBound);

    QFETCH(std::vector<double>, expectedXAxisData);
    QFETCH(std::vector<double>, expectedValuesData);

    // Executes method (xAxisData and valuesData are modified)
    DataSeriesUtils::fillDataHoles(xAxisData, valuesData, resolution, fillValue, minBound,
                                   maxBound);

    // Checks results
    auto equal = [](const auto &data, const auto &expectedData) {
        // Compares with NaN values
        return std::equal(data.begin(), data.end(), expectedData.begin(), expectedData.end(),
                          [](const auto &val, const auto &expectedVal) {
                              return (std::isnan(val) && std::isnan(expectedVal))
                                     || val == expectedVal;
                          });
    };
    QVERIFY(equal(xAxisData, expectedXAxisData));
    QVERIFY(equal(valuesData, expectedValuesData));
}

QTEST_MAIN(TestDataSeriesUtils)
#include "TestDataSeriesUtils.moc"
