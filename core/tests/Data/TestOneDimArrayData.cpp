#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

class TestOneDimArrayData : public QObject {
    Q_OBJECT
private slots:
    /// Tests @sa ArrayData::data(int componentIndex)
    void testDataByComponentIndex_data();
    void testDataByComponentIndex();

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

QTEST_MAIN(TestOneDimArrayData)
#include "TestOneDimArrayData.moc"
