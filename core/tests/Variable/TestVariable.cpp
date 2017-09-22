#include <Variable/Variable.h>

#include <QObject>
#include <QtTest>

#include <memory>

class TestVariable : public QObject {
    Q_OBJECT

private slots:
    void testNotInCacheRangeList();

    void testInCacheRangeList();
};


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
