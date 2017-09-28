#include <Variable/Variable.h>

#include <Data/ScalarSeries.h>

#include <QObject>
#include <QtTest>

#include <memory>

Q_DECLARE_METATYPE(std::shared_ptr<ScalarSeries>)

class TestVariable : public QObject {
    Q_OBJECT

private slots:
    void testClone_data();
    void testClone();

    void testNotInCacheRangeList();
    void testInCacheRangeList();
};

void TestVariable::testClone_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QString>("name");
    QTest::addColumn<QVariantHash>("metadata");
    QTest::addColumn<SqpRange>("range");
    QTest::addColumn<SqpRange>("cacheRange");
    QTest::addColumn<std::shared_ptr<ScalarSeries> >("dataSeries");

    // ////////// //
    // Test cases //
    // ////////// //

    /// Generates a date in double
    auto date = [](int year, int month, int day, int hours, int minutes, int seconds) {
        return DateUtils::secondsSinceEpoch(
            QDateTime{{year, month, day}, {hours, minutes, seconds}, Qt::UTC});
    };

    /// Generates a data series for a range
    auto dataSeries = [](const SqpRange &range) {
        auto xAxisData = std::vector<double>{};
        auto valuesData = std::vector<double>{};

        auto value = 0;
        for (auto x = range.m_TStart; x < range.m_TEnd; ++x, ++value) {
            xAxisData.push_back(x);
            valuesData.push_back(value);
        }

        return std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData), Unit{},
                                              Unit{});
    };

    auto cacheRange = SqpRange{date(2017, 1, 1, 12, 0, 0), date(2017, 1, 1, 13, 0, 0)};
    QTest::newRow("clone1") << QStringLiteral("var1")
                            << QVariantHash{{"data1", 1}, {"data2", "abc"}}
                            << SqpRange{date(2017, 1, 1, 12, 30, 0), (date(2017, 1, 1, 12, 45, 0))}
                            << cacheRange << dataSeries(cacheRange);
}

void TestVariable::testClone()
{
    // Creates variable
    QFETCH(QString, name);
    QFETCH(QVariantHash, metadata);
    QFETCH(SqpRange, range);
    QFETCH(SqpRange, cacheRange);
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

    auto sqpR = SqpRange{DateUtils::secondsSinceEpoch(varRS), DateUtils::secondsSinceEpoch(varRE)};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};

    auto sqpCR
        = SqpRange{DateUtils::secondsSinceEpoch(varCRS), DateUtils::secondsSinceEpoch(varCRE)};

    Variable var{"Var test"};
    var.setRange(sqpR);
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};

    auto notInCach = var.provideNotInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 1);

    auto notInCachRange = notInCach.first();

    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRS));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);


    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRE));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
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

    auto sqpR = SqpRange{DateUtils::secondsSinceEpoch(varRS), DateUtils::secondsSinceEpoch(varRE)};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqpCR
        = SqpRange{DateUtils::secondsSinceEpoch(varCRS), DateUtils::secondsSinceEpoch(varCRE)};

    Variable var{"Var test"};
    var.setRange(sqpR);
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};

    auto notInCach = var.provideInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 0);

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    auto notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRS));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(te));

    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(ts));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRE));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{DateUtils::secondsSinceEpoch(ts), DateUtils::secondsSinceEpoch(te)};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, DateUtils::secondsSinceEpoch(varCRS));
    QCOMPARE(notInCachRange.m_TEnd, DateUtils::secondsSinceEpoch(varCRE));
}


QTEST_MAIN(TestVariable)
#include "TestVariable.moc"
