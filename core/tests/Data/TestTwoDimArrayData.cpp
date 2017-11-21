#include "Data/ArrayData.h"
#include <QObject>
#include <QtTest>

using DataContainer = std::vector<double>;
using Container = std::vector<DataContainer>;
using InputData = QPair<DataContainer, int>;

namespace {

InputData flatten(const Container &container)
{
    if (container.empty()) {
        return {};
    }

    // We assume here that each component of the container have the same size
    auto containerSize = container.size();
    auto componentSize = container.front().size();

    auto result = DataContainer{};
    result.reserve(componentSize * containerSize);

    for (auto i = 0u; i < componentSize; ++i) {
        for (auto j = 0u; j < containerSize; ++j) {
            result.push_back(container.at(j).at(i));
        }
    }

    return {result, static_cast<int>(containerSize)};
}

void verifyArrayData(const ArrayData<2> &arrayData, const Container &expectedData)
{
    auto verifyComponent = [&arrayData](const auto &componentData, const auto &equalFun) {
        QVERIFY(std::equal(arrayData.cbegin(), arrayData.cend(), componentData.cbegin(),
                           componentData.cend(),
                           [&equalFun](const auto &dataSeriesIt, const auto &expectedValue) {
                               return equalFun(dataSeriesIt, expectedValue);
                           }));
    };

    for (auto i = 0u; i < expectedData.size(); ++i) {
        verifyComponent(expectedData.at(i), [i](const auto &seriesIt, const auto &value) {
            return seriesIt.at(i) == value;
        });
    }
}

} // namespace

class TestTwoDimArrayData : public QObject {
    Q_OBJECT
private slots:
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

void TestTwoDimArrayData::testCtor_data()
{
    // Test structure
    QTest::addColumn<InputData>("inputData");    // array data's input
    QTest::addColumn<bool>("success");           // array data has been successfully constructed
    QTest::addColumn<Container>("expectedData"); // expected array data (when success)

    // Test cases
    QTest::newRow("validInput") << flatten(Container{{1., 2., 3., 4., 5.},
                                                     {6., 7., 8., 9., 10.},
                                                     {11., 12., 13., 14., 15.}})
                                << true << Container{{1., 2., 3., 4., 5.},
                                                     {6., 7., 8., 9., 10.},
                                                     {11., 12., 13., 14., 15.}};
    QTest::newRow("invalidInput (invalid data size") << InputData{{1., 2., 3., 4., 5., 6., 7.}, 3}
                                                     << false << Container{{}, {}, {}};
    QTest::newRow("invalidInput (less than two components")
        << flatten(Container{{1., 2., 3., 4., 5.}}) << false << Container{{}, {}, {}};
}

void TestTwoDimArrayData::testCtor()
{
    QFETCH(InputData, inputData);
    QFETCH(bool, success);

    if (success) {
        QFETCH(Container, expectedData);

        ArrayData<2> arrayData{inputData.first, inputData.second};
        verifyArrayData(arrayData, expectedData);
    }
    else {
        QVERIFY_EXCEPTION_THROWN(ArrayData<2>(inputData.first, inputData.second),
                                 std::invalid_argument);
    }
}

void TestTwoDimArrayData::testAdd_data()
{
    // Test structure
    QTest::addColumn<InputData>("inputData");    // array's data input
    QTest::addColumn<InputData>("otherData");    // array data's input to merge with
    QTest::addColumn<bool>("prepend");           // prepend or append merge
    QTest::addColumn<Container>("expectedData"); // expected data after merge

    // Test cases
    auto inputData = flatten(
        Container{{1., 2., 3., 4., 5.}, {11., 12., 13., 14., 15.}, {21., 22., 23., 24., 25.}});

    auto vectorContainer = flatten(Container{{6., 7., 8.}, {16., 17., 18.}, {26., 27., 28}});
    auto tensorContainer = flatten(Container{{6., 7., 8.},
                                             {16., 17., 18.},
                                             {26., 27., 28},
                                             {36., 37., 38.},
                                             {46., 47., 48.},
                                             {56., 57., 58}});

    QTest::newRow("appendMerge") << inputData << vectorContainer << false
                                 << Container{{1., 2., 3., 4., 5., 6., 7., 8.},
                                              {11., 12., 13., 14., 15., 16., 17., 18.},
                                              {21., 22., 23., 24., 25., 26., 27., 28}};
    QTest::newRow("prependMerge") << inputData << vectorContainer << true
                                  << Container{{6., 7., 8., 1., 2., 3., 4., 5.},
                                               {16., 17., 18., 11., 12., 13., 14., 15.},
                                               {26., 27., 28, 21., 22., 23., 24., 25.}};
    QTest::newRow("invalidMerge") << inputData << tensorContainer << false
                                  << Container{{1., 2., 3., 4., 5.},
                                               {11., 12., 13., 14., 15.},
                                               {21., 22., 23., 24., 25.}};
}

void TestTwoDimArrayData::testAdd()
{
    QFETCH(InputData, inputData);
    QFETCH(InputData, otherData);
    QFETCH(bool, prepend);
    QFETCH(Container, expectedData);

    ArrayData<2> arrayData{inputData.first, inputData.second};
    ArrayData<2> other{otherData.first, otherData.second};

    arrayData.add(other, prepend);

    verifyArrayData(arrayData, expectedData);
}

void TestTwoDimArrayData::testClear_data()
{
    // Test structure
    QTest::addColumn<InputData>("inputData"); // array data's input

    // Test cases
    QTest::newRow("data1") << flatten(
        Container{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}});
}

void TestTwoDimArrayData::testClear()
{
    QFETCH(InputData, inputData);

    ArrayData<2> arrayData{inputData.first, inputData.second};
    arrayData.clear();

    auto emptyData = Container(inputData.second, DataContainer{});
    verifyArrayData(arrayData, emptyData);
}

void TestTwoDimArrayData::testSize_data()
{
    // Test structure
    QTest::addColumn<InputData>("inputData"); // array data's input
    QTest::addColumn<int>("expectedSize");    // expected array data size

    // Test cases
    QTest::newRow("data1") << flatten(Container{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}}) << 5;
    QTest::newRow("data2") << flatten(Container{{1., 2., 3., 4., 5.},
                                                {6., 7., 8., 9., 10.},
                                                {11., 12., 13., 14., 15.}})
                           << 5;
}

void TestTwoDimArrayData::testSize()
{
    QFETCH(InputData, inputData);
    QFETCH(int, expectedSize);

    ArrayData<2> arrayData{inputData.first, inputData.second};
    QVERIFY(arrayData.size() == expectedSize);
}

void TestTwoDimArrayData::testSort_data()
{
    // Test structure
    QTest::addColumn<InputData>("inputData");               // array data's input
    QTest::addColumn<std::vector<int> >("sortPermutation"); // permutation used to sort data
    QTest::addColumn<Container>("expectedData");            // expected data after sorting

    // Test cases
    QTest::newRow("data1")
        << flatten(
               Container{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}})
        << std::vector<int>{0, 2, 3, 1, 4}
        << Container{{1., 3., 4., 2., 5.}, {6., 8., 9., 7., 10.}, {11., 13., 14., 12., 15.}};
    QTest::newRow("data2")
        << flatten(
               Container{{1., 2., 3., 4., 5.}, {6., 7., 8., 9., 10.}, {11., 12., 13., 14., 15.}})
        << std::vector<int>{2, 4, 3, 0, 1}
        << Container{{3., 5., 4., 1., 2.}, {8., 10., 9., 6., 7.}, {13., 15., 14., 11., 12.}};
}

void TestTwoDimArrayData::testSort()
{
    QFETCH(InputData, inputData);
    QFETCH(std::vector<int>, sortPermutation);
    QFETCH(Container, expectedData);

    ArrayData<2> arrayData{inputData.first, inputData.second};
    auto sortedArrayData = arrayData.sort(sortPermutation);
    QVERIFY(sortedArrayData != nullptr);

    verifyArrayData(*sortedArrayData, expectedData);
}

QTEST_MAIN(TestTwoDimArrayData)
#include "TestTwoDimArrayData.moc"
