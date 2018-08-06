#include <Variable/Variable.h>

#include <Data/ScalarSeries.h>

#include <QObject>
#include <QtTest>

#include <memory>

namespace {

/// Generates a date in double
auto date = [](int year, int month, int day, int hours, int minutes, int seconds) {
    return DateUtils::secondsSinceEpoch(
        QDateTime{{year, month, day}, {hours, minutes, seconds}, Qt::UTC});
};

/// Generates a series of test data for a range
std::shared_ptr<ScalarSeries> dataSeries(const DateTimeRange &range)
{
    auto xAxisData = std::vector<double>{};
    auto valuesData = std::vector<double>{};

    auto value = 0;
    for (auto x = range.m_TStart; x <= range.m_TEnd; ++x, ++value) {
        xAxisData.push_back(x);
        valuesData.push_back(value);
    }

    return std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData), Unit{},
                                          Unit{});
}

} // namespace

Q_DECLARE_METATYPE(std::shared_ptr<ScalarSeries>)

class TestVariable : public QObject {
    Q_OBJECT

private slots:
    void testClone_data();
    void testClone();

    void testNotInCacheRangeList();
    void testInCacheRangeList();

    void testNbPoints_data();
    void testNbPoints();

    void testRealRange_data();
    void testRealRange();
};

void TestVariable::testClone_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QString>("name");
    QTest::addColumn<QVariantHash>("metadata");
    QTest::addColumn<DateTimeRange>("range");
    QTest::addColumn<DateTimeRange>("cacheRange");
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");

    // ////////// //
    // Test cases //
    // ////////// //

    auto cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 13, 0, 0)};
    QTest::newRow("clone1") << QStringLiteral("var1")
                            << QVariantHash{{"data1", 1}, {"data2", "abc"}}
                            << DateTimeRange{date(2017, 1, 1, 12, 30, 0), (date(2017, 1, 1, 12, 45, 0))}
                            << cacheRange << dataSeries(cacheRange);
}

void TestVariable::testClone()
{
    // Creates variable
    QFETCH(QString, name);
    QFETCH(QVariantHash, metadata);
    QFETCH(DateTimeRange, range);
    QFETCH(DateTimeRange, cacheRange);
    QFETCH(std::shared_ptr<ScalarSeries>, dataSeries);

    Variable variable{name, metadata};
    variable.setRange(range);
    variable.setCacheRange(cacheRange);
    variable.mergeDataSeries(dataSeries);

    // Clones variable
    auto clone = variable.clone();

    // Checks cloned variable's state
    QCOMPARE(clone->name(), name);
    QCOMPARE(clone->metadata(), metadata);
    QCOMPARE(clone->range(), range);
    QCOMPARE(clone->cacheRange(), cacheRange);

    // Compares data series
    if (dataSeries != nullptr) {
        QVERIFY(clone->dataSeries() != nullptr);
        QVERIFY(std::equal(dataSeries->cbegin(), dataSeries->cend(), clone->dataSeries()->cbegin(),
                           clone->dataSeries()->cend(), [](const auto &it1, const auto &it2) {
                               return it1.x() == it2.x() && it1.value() == it2.value();
                           }));
    }
    else {
        QVERIFY(clone->dataSeries() == nullptr);
    }
}

void TestVariable::testNotInCacheRangeList()
{
    auto varRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    auto varRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 40, 0}};

    auto sqpR = DateTimeRange{DateUtils::secondsSinceEpoch(varRS), DateUtils::secondsSinceEpoch(varRE)};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};

    auto sqpCR
        = DateTimeRange{DateUtils::secondsSinceEpoch(varCRS), DateUtils::secondsSinceEpoch(varCRE)};

    Variable var{"Var test"};
    var.setRange(sqpR);
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};

    auto notInCach = var.provideNotInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 1);

    auto notInCachRange = notInCach.first();

    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRS));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);


    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRE));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 2);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRS));
    notInCachRange = notInCach[1];
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRE));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));
}


void TestVariable::testInCacheRangeList()
{
    auto varRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    auto varRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 40, 0}};

    auto sqpR = DateTimeRange{DateUtils::secondsSinceEpoch(varRS), DateUtils::secondsSinceEpoch(varRE)};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqpCR
        = DateTimeRange{DateUtils::secondsSinceEpoch(varCRS), DateUtils::secondsSinceEpoch(varCRE)};

    Variable var{"Var test"};
    var.setRange(sqpR);
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};

    auto notInCach = var.provideInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 0);

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    auto notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRS));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRE));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = DateTimeRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRS));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRE));
}

namespace {

/// Struct used to represent an operation for @sa TestVariable::testNbPoints()
struct NbPointsOperation {
    DateTimeRange m_CacheRange;                      /// Range to set for the variable
    std::shared_ptr<ScalarSeries> m_DataSeries; /// Series to merge in the variable
    int m_ExpectedNbPoints; /// Number of points in the variable expected after operation
};

using NbPointsOperations = std::vector<NbPointsOperation>;

} // namespace

Q_DECLARE_METATYPE(NbPointsOperations)

void TestVariable::testNbPoints_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<NbPointsOperations>("operations");

    // ////////// //
    // Test cases //
    // ////////// //
    NbPointsOperations operations{};

    // Sets cache range (expected nb points = values data)
    auto cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 12, 0, 9)};
    operations.push_back({cacheRange, dataSeries(cacheRange), 10});

    // Doubles cache but don't add data series (expected nb points don't change)
    cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 12, 0, 19)};
    operations.push_back({cacheRange, dataSeries(INVALID_RANGE), 10});

    // Doubles cache and data series (expected nb points change)
    cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 12, 0, 19)};
    operations.push_back({cacheRange, dataSeries(cacheRange), 20});

    // Decreases cache (expected nb points decreases as the series is purged)
    cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 5), date(2017, 1, 1, 12, 0, 9)};
    operations.push_back({cacheRange, dataSeries(INVALID_RANGE), 5});

    QTest::newRow("nbPoints1") << operations;
}

void TestVariable::testNbPoints()
{
    // Creates variable
    Variable variable{"var"};
    QCOMPARE(variable.nbPoints(), 0);

    QFETCH(NbPointsOperations, operations);
    for (const auto &operation : operations) {
        // Sets cache range and merge data series
        variable.setCacheRange(operation.m_CacheRange);
        if (operation.m_DataSeries != nullptr) {
            variable.mergeDataSeries(operation.m_DataSeries);
        }

        // Checks nb points
        QCOMPARE(variable.nbPoints(), operation.m_ExpectedNbPoints);
    }
}

namespace {

/// Struct used to represent a range operation on a variable
/// @sa TestVariable::testRealRange()
struct RangeOperation {
    DateTimeRange m_CacheRange;                      /// Range to set for the variable
    std::shared_ptr<ScalarSeries> m_DataSeries; /// Series to merge in the variable
    DateTimeRange m_ExpectedRealRange; /// Real Range expected after operation on the variable
};

using RangeOperations = std::vector<RangeOperation>;

} // namespace

Q_DECLARE_METATYPE(RangeOperations)

void TestVariable::testRealRange_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<RangeOperations>("operations");

    // ////////// //
    // Test cases //
    // ////////// //
    RangeOperations operations{};

    // Inits cache range and data series (expected real range = cache range)
    auto cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 13, 0, 0)};
    operations.push_back({cacheRange, dataSeries(cacheRange), cacheRange});

    // Changes cache range and updates data series (expected real range = cache range)
    cacheRange = DateTimeRange{date(2017, 1, 1, 14, 0, 0), date(2017, 1, 1, 15, 0, 0)};
    operations.push_back({cacheRange, dataSeries(cacheRange), cacheRange});

    // Changes cache range and update data series but with a lower range (expected real range =
    // data series range)
    cacheRange = DateTimeRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 16, 0, 0)};
    auto dataSeriesRange = DateTimeRange{date(2017, 1, 1, 14, 0, 0), date(2017, 1, 1, 15, 0, 0)};
    operations.push_back({cacheRange, dataSeries(dataSeriesRange), dataSeriesRange});

    // Changes cache range but DON'T update data series (expected real range = cache range
    // before operation)
    cacheRange = DateTimeRange{date(2017, 1, 1, 10, 0, 0), date(2017, 1, 1, 17, 0, 0)};
    operations.push_back({cacheRange, nullptr, dataSeriesRange});

    QTest::newRow("realRange1") << operations;
}

void TestVariable::testRealRange()
{
    // Creates variable (real range is invalid)
    Variable variable{"var"};
    QCOMPARE(variable.realRange(), INVALID_RANGE);

    QFETCH(RangeOperations, operations);
    for (const auto &operation : operations) {
        // Sets cache range and merge data series
        variable.setCacheRange(operation.m_CacheRange);
        if (operation.m_DataSeries != nullptr) {
            variable.mergeDataSeries(operation.m_DataSeries);
        }

        // Checks real range
        QCOMPARE(variable.realRange(), operation.m_ExpectedRealRange);
    }
}


QTEST_MAIN(TestVariable)
#include "TestVariable.moc"
