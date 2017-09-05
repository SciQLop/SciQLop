#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

namespace {

using DataContainer = std::vector<double>;

void verifyArrayData(const ArrayData<1> &arrayData, const DataContainer &expectedData)
{
    QVERIFY(std::equal(
        arrayData.cbegin(), arrayData.cend(), expectedData.cbegin(), expectedData.cend(),
        [](const auto &it, const auto &expectedData) { return it.at(0) == expectedData; }));
}

} // namespace

class TestOneDimArrayData : public QObject {
    Q_OBJECT
private slots:
    /// Tests @sa ArrayData::data()
    void testData_data();
    void testData();

    /// Tests @sa ArrayData::add()
    void testAdd_data();
    void testAdd();

    /// Tests @sa ArrayData::at(int index)
    void testAt_data();
    void testAt();

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

void TestOneDimArrayData::testData_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");    // array's data input
    QTest::addColumn<DataContainer>("expectedData"); // expected data

    // Test cases
    QTest::newRow("data1") << DataContainer{1., 2., 3., 4., 5.}
                           << DataContainer{1., 2., 3., 4., 5.};
}

void TestOneDimArrayData::testData()
{
    QFETCH(DataContainer, inputData);
    QFETCH(DataContainer, expectedData);

    ArrayData<1> arrayData{inputData};
    verifyArrayData(arrayData, expectedData);
}

void TestOneDimArrayData::testAdd_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");    // array's data input
    QTest::addColumn<DataContainer>("otherData");    // array data's input to merge with
    QTest::addColumn<bool>("prepend");               // prepend or append merge
    QTest::addColumn<DataContainer>("expectedData"); // expected data after merge

    // Test cases
    QTest::newRow("appendMerge") << DataContainer{1., 2., 3., 4., 5.} << DataContainer{6., 7., 8.}
                                 << false << DataContainer{1., 2., 3., 4., 5., 6., 7., 8.};
    QTest::newRow("prependMerge") << DataContainer{1., 2., 3., 4., 5.} << DataContainer{6., 7., 8.}
                                  << true << DataContainer{6., 7., 8., 1., 2., 3., 4., 5.};
}

void TestOneDimArrayData::testAdd()
{
    QFETCH(DataContainer, inputData);
    QFETCH(DataContainer, otherData);
    QFETCH(bool, prepend);
    QFETCH(DataContainer, expectedData);

    ArrayData<1> arrayData{inputData};
    ArrayData<1> other{otherData};

    arrayData.add(other, prepend);
    verifyArrayData(arrayData, expectedData);
}

void TestOneDimArrayData::testAt_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData"); // array data's input
    QTest::addColumn<int>("index");               // index to retrieve data
    QTest::addColumn<double>("expectedData");     // expected data at index

    // Test cases
    QTest::newRow("data1") << DataContainer{1., 2., 3., 4., 5.} << 0 << 1.;
    QTest::newRow("data2") << DataContainer{1., 2., 3., 4., 5.} << 3 << 4.;
}

void TestOneDimArrayData::testAt()
{
    QFETCH(DataContainer, inputData);
    QFETCH(int, index);
    QFETCH(double, expectedData);

    ArrayData<1> arrayData{inputData};
    QVERIFY(arrayData.at(index) == expectedData);
}

void TestOneDimArrayData::testClear_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData"); // array data's input

    // Test cases
    QTest::newRow("data1") << DataContainer{1., 2., 3., 4., 5.};
}

void TestOneDimArrayData::testClear()
{
    QFETCH(DataContainer, inputData);

    ArrayData<1> arrayData{inputData};
    arrayData.clear();
    verifyArrayData(arrayData, DataContainer{});
}

void TestOneDimArrayData::testSize_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData"); // array data's input
    QTest::addColumn<int>("expectedSize");        // expected array data size

    // Test cases
    QTest::newRow("data1") << DataContainer{1., 2., 3., 4., 5.} << 5;
}

void TestOneDimArrayData::testSize()
{
    QFETCH(DataContainer, inputData);
    QFETCH(int, expectedSize);

    ArrayData<1> arrayData{inputData};
    QVERIFY(arrayData.size() == expectedSize);
}

void TestOneDimArrayData::testSort_data()
{
    // Test structure
    QTest::addColumn<DataContainer>("inputData");           // array data's input
    QTest::addColumn<std::vector<int> >("sortPermutation"); // permutation used to sort data
    QTest::addColumn<DataContainer>("expectedData");        // expected data after sorting

    // Test cases
    QTest::newRow("data1") << DataContainer{1., 2., 3., 4., 5.} << std::vector<int>{0, 2, 3, 1, 4}
                           << DataContainer{1., 3., 4., 2., 5.};
    QTest::newRow("data2") << DataContainer{1., 2., 3., 4., 5.} << std::vector<int>{4, 1, 2, 3, 0}
                           << DataContainer{5., 2., 3., 4., 1.};
}

void TestOneDimArrayData::testSort()
{
    QFETCH(DataContainer, inputData);
    QFETCH(std::vector<int>, sortPermutation);
    QFETCH(DataContainer, expectedData);

    ArrayData<1> arrayData{inputData};
    auto sortedArrayData = arrayData.sort(sortPermutation);
    QVERIFY(sortedArrayData != nullptr);
    verifyArrayData(*sortedArrayData, expectedData);
}

QTEST_MAIN(TestOneDimArrayData)
#include "TestOneDimArrayData.moc"
