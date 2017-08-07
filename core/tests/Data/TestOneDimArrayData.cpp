#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

class TestOneDimArrayData : public QObject {
    Q_OBJECT
private slots:
    /// Tests @sa ArrayData::data(int componentIndex)
    void testDataByComponentIndex_data();
    void testDataByComponentIndex();

    /// Tests @sa ArrayData::add()
    void testAdd_data();
    void testAdd();

};

void TestOneDimArrayData::testDataByComponentIndex_data()
{
    // Test structure
    QTest::addColumn<QVector<double> >("inputData");    // array data's input
    QTest::addColumn<int>("componentIndex");            // component index to test
    QTest::addColumn<QVector<double> >("expectedData"); // expected data

    // Test cases
    QTest::newRow("validIndex") << QVector<double>{1., 2., 3., 4., 5.} << 0
                                << QVector<double>{1., 2., 3., 4., 5.};
    QTest::newRow("invalidIndex1")
        << QVector<double>{1., 2., 3., 4., 5.} << -1 << QVector<double>{};
    QTest::newRow("invalidIndex2") << QVector<double>{1., 2., 3., 4., 5.} << 1 << QVector<double>{};
}

void TestOneDimArrayData::testDataByComponentIndex()
{
    QFETCH(QVector<double>, inputData);
    QFETCH(int, componentIndex);
    QFETCH(QVector<double>, expectedData);

    ArrayData<1> arrayData{inputData};
    QVERIFY(arrayData.data(componentIndex) == expectedData);
}

void TestOneDimArrayData::testAdd_data()
{
    // Test structure
    QTest::addColumn<QVector<double> >("inputData");    // array's data input
    QTest::addColumn<QVector<double> >("otherData");    // array data's input to merge with
    QTest::addColumn<bool>("prepend");                  // prepend or append merge
    QTest::addColumn<QVector<double> >("expectedData"); // expected data after merge

    // Test cases
    QTest::newRow("appendMerge") << QVector<double>{1., 2., 3., 4., 5.}
                                 << QVector<double>{6., 7., 8.} << false
                                 << QVector<double>{1., 2., 3., 4., 5., 6., 7., 8.};
    QTest::newRow("prependMerge") << QVector<double>{1., 2., 3., 4., 5.}
                                  << QVector<double>{6., 7., 8.} << true
                                  << QVector<double>{6., 7., 8., 1., 2., 3., 4., 5.};
}

void TestOneDimArrayData::testAdd()
{
    QFETCH(QVector<double>, inputData);
    QFETCH(QVector<double>, otherData);
    QFETCH(bool, prepend);
    QFETCH(QVector<double>, expectedData);

    ArrayData<1> arrayData{inputData};
    ArrayData<1> other{otherData};

    arrayData.add(other, prepend);
    QVERIFY(arrayData.data() == expectedData);
}

QTEST_MAIN(TestOneDimArrayData)
#include "TestOneDimArrayData.moc"
