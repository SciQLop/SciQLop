#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

using DataContainer = QVector<QVector<double> >;

class TestTwoDimArrayData : public QObject {
    Q_OBJECT
private slots:
    /// Tests @sa ArrayData::data(int componentIndex)
    void testDataByComponentIndex_data();
    void testDataByComponentIndex();

};

void TestTwoDimArrayData::testDataByComponentIndex_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");       // array data's input
    QTest::addColumn<int>("componentIndex");            // component index to test
    QTest::addColumn<QVector<double> >("expectedData"); // expected data

    // Test cases
    auto inputData
        = DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}};

    QTest::newRow("validIndex1") << inputData << 0 << QVector<double>{1., 2., 3., 4., 5.};
    QTest::newRow("validIndex2") << inputData << 1 << QVector<double>{6., 7., 8., 9., 10.};
    QTest::newRow("validIndex3") << inputData << 2 << QVector<double>{11., 12., 13., 14., 15.};
    QTest::newRow("invalidIndex1") << inputData << -1 << QVector<double>{};
    QTest::newRow("invalidIndex2") << inputData << 3 << QVector<double>{};
}

void TestTwoDimArrayData::testDataByComponentIndex()
{
    QFETCH(DataContainer, inputData);
    QFETCH(int, componentIndex);
    QFETCH(QVector<double>, expectedData);

    ArrayData<2> arrayData{inputData};
    QVERIFY(arrayData.data(componentIndex) == expectedData);
}

QTEST_MAIN(TestTwoDimArrayData)
#include "TestTwoDimArrayData.moc"
