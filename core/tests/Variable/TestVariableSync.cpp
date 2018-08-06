#include <QObject>
#include <QtTest>

#include <memory>

#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <Data/ScalarSeries.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>
#include <Variable/VariableModel.h>

namespace {

/// Delay after each operation on the variable before validating it (in ms)
const auto OPERATION_DELAY = 100;

/**
 * Generates values according to a range. The value generated for a time t is the number of seconds
 * of difference between t and a reference value (which is midnight -> 00:00:00)
 *
 * Example: For a range between 00:00:10 and 00:00:20, the generated values are
 * {10,11,12,13,14,15,16,17,18,19,20}
 */
std::vector<double> values(const DateTimeRange &range)
{
    QTime referenceTime{0, 0};

    std::vector<double> result{};

    for (auto i = range.m_TStart; i <= range.m_TEnd; ++i) {
        auto time = DateUtils::dateTime(i).time();
        result.push_back(referenceTime.secsTo(time));
    }

    return result;
}

void validateRanges(VariableController &variableController,
                    const std::map<int, DateTimeRange> &expectedRanges)
{
    for (const auto &expectedRangeEntry : expectedRanges) {
        auto variableIndex = expectedRangeEntry.first;
        auto expectedRange = expectedRangeEntry.second;

        // Gets the variable in the controller
        auto variable = variableController.variableModel()->variable(variableIndex);

        // Compares variable's range to the expected range
        QVERIFY(variable != nullptr);
        auto range = variable->range();
        qInfo() << "range vs expected range" << range << expectedRange;
        QCOMPARE(range, expectedRange);

        // Compares variable's data with values expected for its range
        auto dataSeries = variable->dataSeries();
        QVERIFY(dataSeries != nullptr);

        auto it = dataSeries->xAxisRange(range.m_TStart, range.m_TEnd);
        auto expectedValues = values(range);
        qInfo() << std::distance(it.first, it.second) << expectedValues.size();
        QVERIFY(std::equal(it.first, it.second, expectedValues.cbegin(), expectedValues.cend(),
                           [](const auto &dataSeriesIt, const auto &expectedValue) {
                               return dataSeriesIt.value() == expectedValue;
                           }));
    }
}

/// Provider used for the tests
class TestProvider : public IDataProvider {
    std::shared_ptr<IDataProvider> clone() const { return std::make_shared<TestProvider>(); }

    void requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters) override
    {
        const auto &ranges = parameters.m_Times;

        for (const auto &range : ranges) {
            // Generates data series
            auto valuesData = values(range);

            std::vector<double> xAxisData{};
            for (auto i = range.m_TStart; i <= range.m_TEnd; ++i) {
                xAxisData.push_back(i);
            }

            auto dataSeries = std::make_shared<ScalarSeries>(
                std::move(xAxisData), std::move(valuesData), Unit{"t", true}, Unit{});

            emit dataProvided(acqIdentifier, dataSeries, range);
        }
    }

    void requestDataAborting(QUuid acqIdentifier) override
    {
        // Does nothing
    }
};

/**
 * Interface representing an operation performed on a variable controller.
 * This interface is used in tests to apply a set of operations and check the status of the
 * controller after each operation
 */
struct IOperation {
    virtual ~IOperation() = default;
    /// Executes the operation on the variable controller
    virtual void exec(VariableController &variableController) const = 0;
};

/**
 *Variable creation operation in the controller
 */
struct Create : public IOperation {
    explicit Create(int index, const DateTimeRange &range) : m_Index{index},m_range(range) {}

    void exec(VariableController &variableController) const override
    {
        auto variable = variableController.createVariable(QString::number(m_Index), {},
                                                          std::make_unique<TestProvider>(), m_range);
    }
    int m_Index; ///< The index of the variable to create in the controller
    DateTimeRange m_range;
};

/**
 * Variable move/shift operation in the controller
 */
struct Move : public IOperation {
    explicit Move(int index, const DateTimeRange &newRange, bool shift = false, int delayMS = 10)
            : m_Index{index}, m_NewRange{newRange}, m_Shift{shift}, m_DelayMs{delayMS}
    {
    }

    void exec(VariableController &variableController) const override
    {
        if (auto variable = variableController.variableModel()->variable(m_Index)) {
            variableController.onRequestDataLoading({variable}, m_NewRange, !m_Shift);
            QTest::qWait(m_DelayMs);
        }
    }

    int m_Index;         ///< The index of the variable to move
    DateTimeRange m_NewRange; ///< The new range of the variable
    bool m_Shift;        ///< Performs a shift (
    int m_DelayMs;       ///< wait the delay after running the request (
};

/**
 * Variable synchronization/desynchronization operation in the controller
 */
struct Synchronize : public IOperation {
    explicit Synchronize(int index, QUuid syncId, bool synchronize = true)
            : m_Index{index}, m_SyncId{syncId}, m_Synchronize{synchronize}
    {
    }

    void exec(VariableController &variableController) const override
    {
        if (auto variable = variableController.variableModel()->variable(m_Index)) {
            if (m_Synchronize) {
                variableController.onAddSynchronized(variable, m_SyncId);
            }
            else {
                variableController.desynchronize(variable, m_SyncId);
            }
        }
    }

    int m_Index;        ///< The index of the variable to sync/desync
    QUuid m_SyncId;     ///< The synchronization group of the variable
    bool m_Synchronize; ///< Performs sync or desync operation
};

/**
 * Test Iteration
 *
 * A test iteration includes an operation to be performed, and a set of expected ranges after each
 * operation. Each range is tested after the operation to ensure that:
 * - the range of the variable is the expected range
 * - the data of the variable are those generated for the expected range
 */
struct Iteration {
    std::shared_ptr<IOperation> m_Operation;  ///< Operation to perform
    std::map<int, DateTimeRange> m_ExpectedRanges; ///< Expected ranges (by variable index)
};

using Iterations = std::vector<Iteration>;

} // namespace

Q_DECLARE_METATYPE(Iterations)

class TestVariableSync : public QObject {
    Q_OBJECT

private slots:
    void initTestCase() { QSKIP("Temporarily disables TestVariableSync"); }

    /// Input data for @sa testSync()
    void testSync_data();

    /// Input data for @sa testSyncOneVar()
    void testSyncOneVar_data();

    /// Tests synchronization between variables through several operations
    void testSync();

    /// Tests synchronization between variables through several operations
    void testSyncOneVar();
};

namespace {

void testSyncCase1()
{
    // Id used to synchronize variables in the controller
    auto syncId = QUuid::createUuid();

    /// Generates a range according to a start time and a end time (the date is the same)
    auto range = [](const QTime &startTime, const QTime &endTime) {
        return DateTimeRange{DateUtils::secondsSinceEpoch(QDateTime{{2017, 1, 1}, startTime, Qt::UTC}),
                        DateUtils::secondsSinceEpoch(QDateTime{{2017, 1, 1}, endTime, Qt::UTC})};
    };

    auto initialRange = range({12, 0}, {13, 0});

    Iterations iterations{};
    // Creates variables var0, var1 and var2
    iterations.push_back({std::make_shared<Create>(0, initialRange), {{0, initialRange}}});
    iterations.push_back({std::make_shared<Create>(1, initialRange), {{0, initialRange}, {1, initialRange}}});
    iterations.push_back(
        {std::make_shared<Create>(2, initialRange), {{0, initialRange}, {1, initialRange}, {2, initialRange}}});

    // Adds variables into the sync group (ranges don't need to be tested here)
    iterations.push_back({std::make_shared<Synchronize>(0, syncId)});
    iterations.push_back({std::make_shared<Synchronize>(1, syncId)});
    iterations.push_back({std::make_shared<Synchronize>(2, syncId)});

    // Moves var0: ranges of var0, var1 and var2 change
    auto newRange = range({12, 30}, {13, 30});
    iterations.push_back(
        {std::make_shared<Move>(0, newRange), {{0, newRange}, {1, newRange}, {2, newRange}}});

    // Moves var1: ranges of var0, var1 and var2 change
    newRange = range({13, 0}, {14, 0});
    iterations.push_back(
        {std::make_shared<Move>(0, newRange), {{0, newRange}, {1, newRange}, {2, newRange}}});

    // Moves var2: ranges of var0, var1 and var2 change
    newRange = range({13, 30}, {14, 30});
    iterations.push_back(
        {std::make_shared<Move>(0, newRange), {{0, newRange}, {1, newRange}, {2, newRange}}});

    // Desyncs var2 and moves var0:
    // - ranges of var0 and var1 change
    // - range of var2 doesn't change anymore
    auto var2Range = newRange;
    newRange = range({13, 45}, {14, 45});
    iterations.push_back({std::make_shared<Synchronize>(2, syncId, false)});
    iterations.push_back(
        {std::make_shared<Move>(0, newRange), {{0, newRange}, {1, newRange}, {2, var2Range}}});

    // Shifts var0: although var1 is synchronized with var0, its range doesn't change
    auto var1Range = newRange;
    newRange = range({14, 45}, {15, 45});
    iterations.push_back({std::make_shared<Move>(0, newRange, true),
                          {{0, newRange}, {1, var1Range}, {2, var2Range}}});

    // Moves var0 through several operations:
    // - range of var0 changes
    // - range or var1 changes according to the previous shift (one hour)
    auto moveVar0 = [&iterations](const auto &var0NewRange, const auto &var1ExpectedRange) {
        iterations.push_back(
            {std::make_shared<Move>(0, var0NewRange), {{0, var0NewRange}, {1, var1ExpectedRange}}});
    };

    // Pan left
    moveVar0(range({14, 30}, {15, 30}), range({13, 30}, {14, 30}));
    // Pan right
    moveVar0(range({16, 0}, {17, 0}), range({15, 0}, {16, 0}));
    // Zoom in
    moveVar0(range({16, 30}, {16, 45}), range({15, 30}, {15, 45}));
    // Zoom out
    moveVar0(range({16, 15}, {17, 0}), range({15, 15}, {16, 0}));

    QTest::newRow("sync1") << syncId << initialRange << std::move(iterations) << 200;
}

void testSyncCase2()
{
    // Id used to synchronize variables in the controller
    auto syncId = QUuid::createUuid();

    /// Generates a range according to a start time and a end time (the date is the same)
    auto dateTime = [](int year, int month, int day, int hours, int minutes, int seconds) {
        return DateUtils::secondsSinceEpoch(
            QDateTime{{year, month, day}, QTime{hours, minutes, seconds}, Qt::UTC});
    };

    auto initialRange = DateTimeRange{dateTime(2017, 1, 1, 12, 0, 0), dateTime(2017, 1, 1, 13, 0, 0)};

    Iterations iterations{};
    // Creates variables var0 and var1
    iterations.push_back({std::make_shared<Create>(0, initialRange), {{0, initialRange}}});
    iterations.push_back({std::make_shared<Create>(1, initialRange), {{0, initialRange}, {1, initialRange}}});

    // Adds variables into the sync group (ranges don't need to be tested here)
    iterations.push_back({std::make_shared<Synchronize>(0, syncId)});
    iterations.push_back({std::make_shared<Synchronize>(1, syncId)});


    // Moves var0 through several operations:
    // - range of var0 changes
    // - range or var1 changes according to the previous shift (one hour)
    auto moveVar0 = [&iterations](const auto &var0NewRange) {
        iterations.push_back(
            {std::make_shared<Move>(0, var0NewRange), {{0, var0NewRange}, {1, var0NewRange}}});
    };
    moveVar0(DateTimeRange{dateTime(2017, 1, 1, 12, 0, 0), dateTime(2017, 1, 1, 13, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 1, 14, 0, 0), dateTime(2017, 1, 1, 15, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 1, 8, 0, 0), dateTime(2017, 1, 1, 9, 0, 0)});
    //    moveVar0(SqpRange{dateTime(2017, 1, 1, 7, 30, 0), dateTime(2017, 1, 1, 9, 30, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 1, 2, 0, 0), dateTime(2017, 1, 1, 4, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 1, 6, 0, 0), dateTime(2017, 1, 1, 8, 0, 0)});

    moveVar0(DateTimeRange{dateTime(2017, 1, 10, 6, 0, 0), dateTime(2017, 1, 15, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 17, 6, 0, 0), dateTime(2017, 1, 25, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 2, 6, 0, 0), dateTime(2017, 1, 8, 8, 0, 0)});

    moveVar0(DateTimeRange{dateTime(2017, 4, 10, 6, 0, 0), dateTime(2017, 6, 15, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 17, 6, 0, 0), dateTime(2017, 2, 25, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 7, 2, 6, 0, 0), dateTime(2017, 10, 8, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 4, 10, 6, 0, 0), dateTime(2017, 6, 15, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 17, 6, 0, 0), dateTime(2017, 2, 25, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 7, 2, 6, 0, 0), dateTime(2017, 10, 8, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 4, 10, 6, 0, 0), dateTime(2017, 6, 15, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 17, 6, 0, 0), dateTime(2017, 2, 25, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 7, 2, 6, 0, 0), dateTime(2017, 10, 8, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 4, 10, 6, 0, 0), dateTime(2017, 6, 15, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 1, 17, 6, 0, 0), dateTime(2017, 2, 25, 8, 0, 0)});
    moveVar0(DateTimeRange{dateTime(2017, 7, 2, 6, 0, 0), dateTime(2017, 10, 8, 8, 0, 0)});


    QTest::newRow("sync2") << syncId << initialRange << iterations << 4000;
    //    QTest::newRow("sync3") << syncId << initialRange << iterations << 5000;
}

void testSyncOnVarCase1()
{
    // Id used to synchronize variables in the controller
    auto syncId = QUuid::createUuid();

    /// Generates a range according to a start time and a end time (the date is the same)
    auto range = [](const QTime &startTime, const QTime &endTime) {
        return DateTimeRange{DateUtils::secondsSinceEpoch(QDateTime{{2017, 1, 1}, startTime, Qt::UTC}),
                        DateUtils::secondsSinceEpoch(QDateTime{{2017, 1, 1}, endTime, Qt::UTC})};
    };

    auto initialRange = range({12, 0}, {13, 0});

    Iterations creations{};
    // Creates variables var0, var1 and var2
    creations.push_back({std::make_shared<Create>(0, initialRange), {{0, initialRange}}});

    Iterations synchronization{};
    // Adds variables into the sync group (ranges don't need to be tested here)
    synchronization.push_back({std::make_shared<Synchronize>(0, syncId)});

    Iterations iterations{};

    //    Moves var0 through several operations
    auto moveOp = [&iterations](const auto &requestedRange, const auto &expectedRange, auto delay) {
        iterations.push_back(
            {std::make_shared<Move>(0, requestedRange, true, delay), {{0, expectedRange}}});
    };

    // we assume here 300 ms is enough to finsh a operation
    int delayToFinish = 300;
    // jump to right, let's the operation time to finish
    moveOp(range({14, 30}, {15, 30}), range({14, 30}, {15, 30}), delayToFinish);
    // pan to right, let's the operation time to finish
    moveOp(range({14, 45}, {15, 45}), range({14, 45}, {15, 45}), delayToFinish);
    // jump to left, let's the operation time to finish
    moveOp(range({03, 30}, {04, 30}), range({03, 30}, {04, 30}), delayToFinish);
    // Pan to left, let's the operation time to finish
    moveOp(range({03, 10}, {04, 10}), range({03, 10}, {04, 10}), delayToFinish);
    // Zoom in, let's the operation time to finish
    moveOp(range({03, 30}, {04, 00}), range({03, 30}, {04, 00}), delayToFinish);
    // Zoom out left, let's the operation time to finish
    moveOp(range({01, 10}, {18, 10}), range({01, 10}, {18, 10}), delayToFinish);
    // Go back to initial range
    moveOp(initialRange, initialRange, delayToFinish);


    // jump to right, let's the operation time to finish
    //    moveOp(range({14, 30}, {15, 30}), initialRange, delayToFinish);
    // Zoom out left, let's the operation time to finish
    moveOp(range({01, 10}, {18, 10}), initialRange, delayToFinish);
    // Go back to initial range
    moveOp(initialRange, initialRange, 300);

    QTest::newRow("syncOnVarCase1") << syncId << initialRange << std::move(creations)
                                    << std::move(iterations);
}
}

void TestVariableSync::testSync_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QUuid>("syncId");
    QTest::addColumn<DateTimeRange>("initialRange");
    QTest::addColumn<Iterations>("iterations");
    QTest::addColumn<int>("operationDelay");

    // ////////// //
    // Test cases //
    // ////////// //

    testSyncCase1();
    testSyncCase2();
}

void TestVariableSync::testSyncOneVar_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QUuid>("syncId");
    QTest::addColumn<DateTimeRange>("initialRange");
    QTest::addColumn<Iterations>("creations");
    QTest::addColumn<Iterations>("iterations");

    // ////////// //
    // Test cases //
    // ////////// //

    testSyncOnVarCase1();
}

void TestVariableSync::testSync()
{
    // Inits controllers
    TimeController timeController{};
    VariableController variableController{};
    //variableController.setTimeController(&timeController);

    QFETCH(QUuid, syncId);
    QFETCH(DateTimeRange, initialRange);
    timeController.setDateTimeRange(initialRange);

    // Synchronization group used
    variableController.onAddSynchronizationGroupId(syncId);

    // For each iteration:
    // - execute operation
    // - compare the variables' state to the expected states
    QFETCH(Iterations, iterations);
    QFETCH(int, operationDelay);
    for (const auto &iteration : iterations) {
        iteration.m_Operation->exec(variableController);
        QTest::qWait(operationDelay);

        validateRanges(variableController, iteration.m_ExpectedRanges);
    }
}

void TestVariableSync::testSyncOneVar()
{
    // Inits controllers
    TimeController timeController{};
    VariableController variableController{};
    //variableController.setTimeController(&timeController);

    QFETCH(QUuid, syncId);
    QFETCH(DateTimeRange, initialRange);
    timeController.setDateTimeRange(initialRange);

    // Synchronization group used
    variableController.onAddSynchronizationGroupId(syncId);

    // For each iteration:
    // - execute operation
    // - compare the variables' state to the expected states
    QFETCH(Iterations, iterations);
    QFETCH(Iterations, creations);

    for (const auto &creation : creations) {
        creation.m_Operation->exec(variableController);
        QTest::qWait(300);
    }

    for (const auto &iteration : iterations) {
        iteration.m_Operation->exec(variableController);
    }

    if (!iterations.empty()) {
        validateRanges(variableController, iterations.back().m_ExpectedRanges);
    }
}

QTEST_MAIN(TestVariableSync)

#include "TestVariableSync.moc"
