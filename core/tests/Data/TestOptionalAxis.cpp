#include <Data/ArrayData.h>
#include <Data/OptionalAxis.h>

#include <QObject>
#include <QtTest>

Q_DECLARE_METATYPE(OptionalAxis)

class TestOptionalAxis : public QObject {
    Q_OBJECT

private slots:
    /// Tests the creation of a undefined axis
    void testNotDefinedAxisCtor();

    /// Tests the creation of a undefined axis
    void testDefinedAxisCtor_data();
    void testDefinedAxisCtor();

    /// Tests @sa OptionalAxis::size() method
    void testSize_data();
    void testSize();

    /// Tests @sa OptionalAxis::unit() method
    void testUnit_data();
    void testUnit();
};

void TestOptionalAxis::testNotDefinedAxisCtor()
{
    OptionalAxis notDefinedAxis{};
    QVERIFY(!notDefinedAxis.isDefined());
}

void TestOptionalAxis::testDefinedAxisCtor_data()
{
    QTest::addColumn<bool>("noData"); // If set to true, nullptr is passed as data of the axis
    QTest::addColumn<std::vector<double> >(
        "data"); // Values assigned to the axis when 'noData' flag is set to false
    QTest::addColumn<Unit>("unit"); // Unit assigned to the axis

    QTest::newRow("validData") << false << std::vector<double>{1, 2, 3} << Unit{"Hz"};
    QTest::newRow("invalidData") << true << std::vector<double>{} << Unit{"Hz"};
}

void TestOptionalAxis::testDefinedAxisCtor()
{
    QFETCH(bool, noData);
    QFETCH(Unit, unit);

    // When there is no data, we expect that the constructor returns exception
    if (noData) {
        QVERIFY_EXCEPTION_THROWN(OptionalAxis(nullptr, unit), std::invalid_argument);
    }
    else {
        QFETCH(std::vector<double>, data);

        OptionalAxis axis{std::make_shared<ArrayData<1> >(data), unit};
        QVERIFY(axis.isDefined());
    }
}

void TestOptionalAxis::testSize_data()
{
    QTest::addColumn<OptionalAxis>("axis"); // Axis used for test case (defined or not)
    QTest::addColumn<int>("expectedSize");  // Expected number of data in the axis

    // Lambda that creates default defined axis (with the values passed in parameter)
    auto axis = [](std::vector<double> values) {
        return OptionalAxis{std::make_shared<ArrayData<1> >(std::move(values)), Unit{"Hz"}};
    };

    QTest::newRow("data1") << axis({}) << 0;
    QTest::newRow("data2") << axis({1, 2, 3}) << 3;
    QTest::newRow("data3") << axis({1, 2, 3, 4}) << 4;
    QTest::newRow("data4 (axis not defined)") << OptionalAxis{}
                                              << 0; // Expects 0 for undefined axis
}

void TestOptionalAxis::testSize()
{
    QFETCH(OptionalAxis, axis);
    QFETCH(int, expectedSize);

    QCOMPARE(axis.size(), expectedSize);
}

void TestOptionalAxis::testUnit_data()
{
    QTest::addColumn<OptionalAxis>("axis"); // Axis used for test case (defined or not)
    QTest::addColumn<Unit>("expectedUnit"); // Expected unit for the axis

    // Lambda that creates default defined axis (with the unit passed in parameter)
    auto axis = [](Unit unit) {
        return OptionalAxis{std::make_shared<ArrayData<1> >(std::vector<double>{1, 2, 3}), unit};
    };

    QTest::newRow("data1") << axis(Unit{"Hz"}) << Unit{"Hz"};
    QTest::newRow("data2") << axis(Unit{"t", true}) << Unit{"t", true};
    QTest::newRow("data3 (axis not defined)") << OptionalAxis{}
                                              << Unit{}; // Expects default unit for undefined axis
}

void TestOptionalAxis::testUnit()
{
    QFETCH(OptionalAxis, axis);
    QFETCH(Unit, expectedUnit);

    QCOMPARE(axis.unit(), expectedUnit);
}

QTEST_MAIN(TestOptionalAxis)
#include "TestOptionalAxis.moc"
