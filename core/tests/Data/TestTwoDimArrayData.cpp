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

    /// Tests @sa ArrayData ctor
    void testCtor_data();
    void testCtor();

    /// Tests @sa ArrayData::add()
    void testAdd_data();
    void testAdd();

    /// Tests @sa ArrayData::clear()
    void testClear_data();
    void testClear();

    /// Tests @sa ArrayData::size()
    void testSize_data();
    void testSize();

    /// Tests @sa ArrayData::sort()
    void testSort_data();
    void testSort();
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

void TestTwoDimArrayData::testCtor_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");    // array data's input
    QTest::addColumn<bool>("success");               // array data has been successfully constructed
    QTest::addColumn<DataContainer>("expectedData"); // expected array data (when success)

    // Test cases
    QTest::newRow("validInput")
        << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}}
        << true
        << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}};
    QTest::newRow("malformedInput (components of the array data haven't the same size")
        << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8.}, {11., 12.}} << true
        << DataContainer{{}, {}, {}};
    QTest::newRow("invalidInput (less than tow components")
        << DataContainer{{1., 2., 3., 4., 5.}} << false << DataContainer{{}, {}, {}};
}

void TestTwoDimArrayData::testCtor()
{
    QFETCH(DataContainer, inputData);
    QFETCH(bool, success);

    if (success) {
        QFETCH(DataContainer, expectedData);

        ArrayData<2> arrayData{inputData};

        for (auto i = 0; i < expectedData.size(); ++i) {
            QVERIFY(arrayData.data(i) == expectedData.at(i));
        }
    }
    else {
        QVERIFY_EXCEPTION_THROWN(ArrayData<2> arrayData{inputData}, std::invalid_argument);
    }
}

void TestTwoDimArrayData::testAdd_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");    // array's data input
    QTest::addColumn<DataContainer>("otherData");    // array data's input to merge with
    QTest::addColumn<bool>("prepend");               // prepend or append merge
    QTest::addColumn<DataContainer>("expectedData"); // expected data after merge

    // Test cases
    auto inputData
        = DataContainer{{1., 2., 3., 4., 5.}, {11., 12., 13., 14., 15.}, {21., 22., 23., 24., 25.}};

    auto vectorContainer = DataContainer{{6., 7., 8.}, {16., 17., 18.}, {26., 27., 28}};
    auto tensorContainer = DataContainer{{6., 7., 8.},    {16., 17., 18.}, {26., 27., 28},
                                         {36., 37., 38.}, {46., 47., 48.}, {56., 57., 58}};

    QTest::newRow("appendMerge") << inputData << vectorContainer << false
                                 << DataContainer{{1., 2., 3., 4., 5., 6., 7., 8.},
                                                  {11., 12., 13., 14., 15., 16., 17., 18.},
                                                  {21., 22., 23., 24., 25., 26., 27., 28}};
    QTest::newRow("prependMerge") << inputData << vectorContainer << true
                                  << DataContainer{{6., 7., 8., 1., 2., 3., 4., 5.},
                                                   {16., 17., 18., 11., 12., 13., 14., 15.},
                                                   {26., 27., 28, 21., 22., 23., 24., 25.}};
    QTest::newRow("invalidMerge") << inputData << tensorContainer << false << inputData;
}

void TestTwoDimArrayData::testAdd()
{
    QFETCH(DataContainer, inputData);
    QFETCH(DataContainer, otherData);
    QFETCH(bool, prepend);
    QFETCH(DataContainer, expectedData);

    ArrayData<2> arrayData{inputData};
    ArrayData<2> other{otherData};

    arrayData.add(other, prepend);

    for (auto i = 0; i < expectedData.size(); ++i) {
        QVERIFY(arrayData.data(i) == expectedData.at(i));
    }
}

void TestTwoDimArrayData::testClear_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData"); // array data's input

    // Test cases
    QTest::newRow("data1") << DataContainer{
        {1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}};
}

void TestTwoDimArrayData::testClear()
{
    QFETCH(DataContainer, inputData);

    ArrayData<2> arrayData{inputData};
    arrayData.clear();

    for (auto i = 0; i < inputData.size(); ++i) {
        QVERIFY(arrayData.data(i) == QVector<double>{});
    }
}

void TestTwoDimArrayData::testSize_data()
{
    // Test structure
    QTest::addColumn<QVector<QVector<double> > >("inputData"); // array data's input
    QTest::addColumn<int>("expectedSize");                     // expected array data size

    // Test cases
    QTest::newRow("data1") << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}} << 5;
    QTest::newRow("data2") << DataContainer{{1., 2., 3., 4., 5.},
                                            {6., 7., 8., 9., 10.},
                                            {11., 12., 13., 14., 15.}}
                           << 5;
}

void TestTwoDimArrayData::testSize()
{
    QFETCH(DataContainer, inputData);
    QFETCH(int, expectedSize);

    ArrayData<2> arrayData{inputData};
    QVERIFY(arrayData.size() == expectedSize);
}

void TestTwoDimArrayData::testSort_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");           // array data's input
    QTest::addColumn<std::vector<int> >("sortPermutation"); // permutation used to sort data
    QTest::addColumn<DataContainer>("expectedData");        // expected data after sorting

    // Test cases
    QTest::newRow("data1")
        << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}}
        << std::vector<int>{0, 2, 3, 1, 4}
        << DataContainer{{1., 3., 4., 2., 5.}, {6., 8., 9., 7., 10.}, {11., 13., 14., 12., 15.}};
    QTest::newRow("data2")
        << DataContainer{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}}
        << std::vector<int>{2, 4, 3, 0, 1}
        << DataContainer{{3., 5., 4., 1., 2.}, {8., 10., 9., 6., 7.}, {13., 15., 14., 11., 12.}};
}

void TestTwoDimArrayData::testSort()
{
    QFETCH(DataContainer, inputData);
    QFETCH(std::vector<int>, sortPermutation);
    QFETCH(DataContainer, expectedData);

    ArrayData<2> arrayData{inputData};
    auto sortedArrayData = arrayData.sort(sortPermutation);
    QVERIFY(sortedArrayData != nullptr);

    for (auto i = 0; i < expectedData.size(); ++i) {
        QVERIFY(sortedArrayData->data(i) == expectedData.at(i));
    }
}

QTEST_MAIN(TestTwoDimArrayData)
#include "TestTwoDimArrayData.moc"
