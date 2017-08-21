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

    auto sqpR = SqpRange{static_cast<double>(varRS.toMSecsSinceEpoch()),
                         static_cast<double>(varRE.toMSecsSinceEpoch())};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqpCR = SqpRange{static_cast<double>(varCRS.toMSecsSinceEpoch()),
                          static_cast<double>(varCRE.toMSecsSinceEpoch())};

    Variable var{"Var test", sqpR};
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                        static_cast<double>(te.toMSecsSinceEpoch())};

    auto notInCach = var.provideNotInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 1);

    auto notInCachRange = notInCach.first();

    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(varCRS.toMSecsSinceEpoch()));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);


    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(varCRE.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideNotInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 2);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(varCRS.toMSecsSinceEpoch()));
    notInCachRange = notInCach[1];
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(varCRE.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));
}


void TestVariable::testInCacheRangeList()
{
    auto varRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    auto varRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 40, 0}};

    auto sqpR = SqpRange{static_cast<double>(varRS.toMSecsSinceEpoch()),
                         static_cast<double>(varRE.toMSecsSinceEpoch())};

    auto varCRS = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto varCRE = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqpCR = SqpRange{static_cast<double>(varCRS.toMSecsSinceEpoch()),
                          static_cast<double>(varCRE.toMSecsSinceEpoch())};

    Variable var{"Var test", sqpR};
    var.setCacheRange(sqpCR);

    // 1: [ts,te] < varTS
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                        static_cast<double>(te.toMSecsSinceEpoch())};

    auto notInCach = var.provideInCacheRangeList(sqp);

    QCOMPARE(notInCach.size(), 0);

    // 2: ts < varTS < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    auto notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(varCRS.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 3: varTS < ts < te < varTE
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 4: varTS < ts < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(varCRE.toMSecsSinceEpoch()));

    // 5: varTS < varTE < ts < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 20, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 0);

    // 6: ts <varTS < varTE < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};
    notInCach = var.provideInCacheRangeList(sqp);
    QCOMPARE(notInCach.size(), 1);
    notInCachRange = notInCach.first();
    QCOMPARE(notInCachRange.m_TStart, static_cast<double>(varCRS.toMSecsSinceEpoch()));
    QCOMPARE(notInCachRange.m_TEnd, static_cast<double>(varCRE.toMSecsSinceEpoch()));
}


QTEST_MAIN(TestVariable)
#include "TestVariable.moc"
