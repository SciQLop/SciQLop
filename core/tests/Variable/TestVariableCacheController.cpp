#include <Variable/Variable.h>
#include <Variable/VariableCacheController.h>

#include <QObject>
#include <QtTest>

#include <memory>

class TestVariableCacheController : public QObject {
    Q_OBJECT

private slots:
    void testProvideNotInCacheDateTimeList();

    void testAddDateTime();
};


void TestVariableCacheController::testProvideNotInCacheDateTimeList()
{
    VariableCacheController variableCacheController{};

    auto ts0 = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto te0 = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqp0 = SqpRange{static_cast<double>(ts0.toMSecsSinceEpoch()),
                         static_cast<double>(te0.toMSecsSinceEpoch())};

    auto ts1 = QDateTime{QDate{2017, 01, 01}, QTime{2, 6, 0, 0}};
    auto te1 = QDateTime{QDate{2017, 01, 01}, QTime{2, 8, 0, 0}};
    auto sqp1 = SqpRange{static_cast<double>(ts1.toMSecsSinceEpoch()),
                         static_cast<double>(te1.toMSecsSinceEpoch())};

    auto ts2 = QDateTime{QDate{2017, 01, 01}, QTime{2, 18, 0, 0}};
    auto te2 = QDateTime{QDate{2017, 01, 01}, QTime{2, 20, 0, 0}};
    auto sqp2 = SqpRange{static_cast<double>(ts2.toMSecsSinceEpoch()),
                         static_cast<double>(te2.toMSecsSinceEpoch())};

    auto var0 = std::make_shared<Variable>("", sqp0);

    variableCacheController.addDateTime(var0, sqp0);
    variableCacheController.addDateTime(var0, sqp1);
    variableCacheController.addDateTime(var0, sqp2);

    // first case [ts,te] < ts0
    auto ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    auto te = QDateTime{QDate{2017, 01, 01}, QTime{2, 1, 0, 0}};
    auto sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                        static_cast<double>(te.toMSecsSinceEpoch())};


    auto notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    auto notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));


    // second case ts < ts0 &&  ts0 < te <= te0
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts0.toMSecsSinceEpoch()));

    // 3th case ts < ts0 &&  te0 < te <= ts1
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 2);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts0.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(1);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 4th case ts < ts0 &&  ts1 < te <= te1
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 7, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 2);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts0.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(1);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts1.toMSecsSinceEpoch()));

    // 5th case ts < ts0 &&  te3 < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 0, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 22, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 4);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts0.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(1);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts1.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(2);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te1.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts2.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(3);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te2.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));


    // 6th case ts2 < ts
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 45, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 47, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 7th case ts = te0 && te < ts1
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 8th case ts0 < ts < te0 && te < ts1
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 9th case ts0 < ts < te0 &&  ts1 < te < te1
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 30, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 7, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te0.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts1.toMSecsSinceEpoch()));

    // 10th case te1 < ts < te < ts2
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 9, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 10, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 1);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 11th case te0 < ts < ts1 &&  te3 < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 47, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};


    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 3);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts1.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(1);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te1.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts2.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(2);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te2.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));

    // 12th case te0 < ts < ts1 &&  te3 < te
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 5, 0, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 10, 0, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};

    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);

    QCOMPARE(notInCach.size(), 2);
    notInCacheSqp = notInCach.first();
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(ts.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(ts1.toMSecsSinceEpoch()));

    notInCacheSqp = notInCach.at(1);
    QCOMPARE(notInCacheSqp.m_TStart, static_cast<double>(te1.toMSecsSinceEpoch()));
    QCOMPARE(notInCacheSqp.m_TEnd, static_cast<double>(te.toMSecsSinceEpoch()));


    // 12th case ts0 < ts < te0
    ts = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 10, 0}};
    te = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 50, 0}};
    sqp = SqpRange{static_cast<double>(ts.toMSecsSinceEpoch()),
                   static_cast<double>(te.toMSecsSinceEpoch())};

    notInCach = variableCacheController.provideNotInCacheDateTimeList(var0, sqp);
    QCOMPARE(notInCach.size(), 0);
}


void TestVariableCacheController::testAddDateTime()
{
    VariableCacheController variableCacheController{};

    auto ts0 = QDateTime{QDate{2017, 01, 01}, QTime{2, 3, 0, 0}};
    auto te0 = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto sqp0 = SqpRange{static_cast<double>(ts0.toMSecsSinceEpoch()),
                         static_cast<double>(te0.toMSecsSinceEpoch())};

    auto ts1 = QDateTime{QDate{2017, 01, 01}, QTime{2, 6, 0, 0}};
    auto te1 = QDateTime{QDate{2017, 01, 01}, QTime{2, 8, 0, 0}};
    auto sqp1 = SqpRange{static_cast<double>(ts1.toMSecsSinceEpoch()),
                         static_cast<double>(te1.toMSecsSinceEpoch())};

    auto ts2 = QDateTime{QDate{2017, 01, 01}, QTime{2, 18, 0, 0}};
    auto te2 = QDateTime{QDate{2017, 01, 01}, QTime{2, 20, 0, 0}};
    auto sqp2 = SqpRange{static_cast<double>(ts2.toMSecsSinceEpoch()),
                         static_cast<double>(te2.toMSecsSinceEpoch())};

    auto ts01 = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto te01 = QDateTime{QDate{2017, 01, 01}, QTime{2, 6, 0, 0}};
    auto sqp01 = SqpRange{static_cast<double>(ts01.toMSecsSinceEpoch()),
                          static_cast<double>(te01.toMSecsSinceEpoch())};

    auto ts3 = QDateTime{QDate{2017, 01, 01}, QTime{2, 14, 0, 0}};
    auto te3 = QDateTime{QDate{2017, 01, 01}, QTime{2, 16, 0, 0}};
    auto sqp3 = SqpRange{static_cast<double>(ts3.toMSecsSinceEpoch()),
                         static_cast<double>(te3.toMSecsSinceEpoch())};

    auto ts03 = QDateTime{QDate{2017, 01, 01}, QTime{2, 4, 0, 0}};
    auto te03 = QDateTime{QDate{2017, 01, 01}, QTime{2, 22, 0, 0}};
    auto sqp03 = SqpRange{static_cast<double>(ts03.toMSecsSinceEpoch()),
                          static_cast<double>(te03.toMSecsSinceEpoch())};


    auto var0 = std::make_shared<Variable>("", sqp0);


    // First case: add the first interval to the variable :sqp0
    variableCacheController.addDateTime(var0, sqp0);
    auto dateCacheList = variableCacheController.dateCacheList(var0);
    QCOMPARE(dateCacheList.count(), 1);
    auto dateCache = dateCacheList.at(0);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts0.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te0.toMSecsSinceEpoch()));

    // 2nd case: add a second interval : sqp1 > sqp0
    variableCacheController.addDateTime(var0, sqp1);
    dateCacheList = variableCacheController.dateCacheList(var0);
    QCOMPARE(dateCacheList.count(), 2);
    dateCache = dateCacheList.at(0);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts0.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te0.toMSecsSinceEpoch()));

    dateCache = dateCacheList.at(1);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts1.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te1.toMSecsSinceEpoch()));

    // 3th case: merge sqp0 & sqp1 with sqp01
    variableCacheController.addDateTime(var0, sqp01);
    dateCacheList = variableCacheController.dateCacheList(var0);
    QCOMPARE(dateCacheList.count(), 1);
    dateCache = dateCacheList.at(0);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts0.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te1.toMSecsSinceEpoch()));


    // 4th case: add a second interval : sqp1 > sqp0
    variableCacheController.addDateTime(var0, sqp2);
    variableCacheController.addDateTime(var0, sqp3);
    dateCacheList = variableCacheController.dateCacheList(var0);
    QCOMPARE(dateCacheList.count(), 3);
    dateCache = dateCacheList.at(0);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts0.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te1.toMSecsSinceEpoch()));

    dateCache = dateCacheList.at(1);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts3.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te3.toMSecsSinceEpoch()));

    dateCache = dateCacheList.at(2);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts2.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te2.toMSecsSinceEpoch()));


    // 5th case: merge all interval
    variableCacheController.addDateTime(var0, sqp03);
    dateCacheList = variableCacheController.dateCacheList(var0);
    QCOMPARE(dateCacheList.count(), 1);
    dateCache = dateCacheList.at(0);
    QCOMPARE(dateCache.m_TStart, static_cast<double>(ts0.toMSecsSinceEpoch()));
    QCOMPARE(dateCache.m_TEnd, static_cast<double>(te03.toMSecsSinceEpoch()));
}


QTEST_MAIN(TestVariableCacheController)
#include "TestVariableCacheController.moc"
