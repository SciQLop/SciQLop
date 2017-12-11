#include "FuzzingDefs.h"
#include "FuzzingOperations.h"
#include "FuzzingUtils.h"

#include "AmdaProvider.h"

#include <Network/NetworkController.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/VariableController.h>

#include <QLoggingCategory>
#include <QObject>
#include <QtTest>

#include <memory>

Q_LOGGING_CATEGORY(LOG_TestAmdaFuzzing, "TestAmdaFuzzing")

namespace {

// /////// //
// Aliases //
// /////// //

using VariableId = int;
using Weight = double;
using Weights = std::vector<Weight>;

using VariableOperation = std::pair<VariableId, std::shared_ptr<IFuzzingOperation> >;
using VariablesOperations = std::vector<VariableOperation>;

using WeightedOperationsPool = std::map<std::shared_ptr<IFuzzingOperation>, Weight>;
using VariablesPool = std::map<VariableId, std::shared_ptr<Variable> >;

// ///////// //
// Constants //
// ///////// //

// Defaults values used when the associated properties have not been set for the test
const auto NB_MAX_OPERATIONS_DEFAULT_VALUE = 100;
const auto NB_MAX_VARIABLES_DEFAULT_VALUE = 1;
const auto AVAILABLE_OPERATIONS_DEFAULT_VALUE
    = QVariant::fromValue(WeightedOperationsTypes{{FuzzingOperationType::CREATE, 1.},
                                                  {FuzzingOperationType::PAN_LEFT, 1.},
                                                  {FuzzingOperationType::PAN_RIGHT, 1.},
                                                  {FuzzingOperationType::ZOOM_IN, 1.},
                                                  {FuzzingOperationType::ZOOM_OUT, 1.}});

/// Delay between each operation (in ms)
const auto OPERATION_DELAY_DEFAULT_VALUE = 3000;

// /////// //
// Methods //
// /////// //

/// Goes through the variables pool and operations pool to determine the set of {variable/operation}
/// pairs that are valid (i.e. operation that can be executed on variable)
std::pair<VariablesOperations, Weights>
availableOperations(const VariablesPool &variablesPool,
                    const WeightedOperationsPool &operationsPool)
{
    VariablesOperations result{};
    Weights weights{};

    for (const auto &variablesPoolEntry : variablesPool) {
        auto variableId = variablesPoolEntry.first;
        auto variable = variablesPoolEntry.second;

        for (const auto &operationsPoolEntry : operationsPool) {
            auto operation = operationsPoolEntry.first;
            auto weight = operationsPoolEntry.second;

            // A pair is valid if the current operation can be executed on the current variable
            if (operation->canExecute(variable)) {
                result.push_back({variableId, operation});
                weights.push_back(weight);
            }
        }
    }

    return {result, weights};
}

WeightedOperationsPool createOperationsPool(const WeightedOperationsTypes &types)
{
    WeightedOperationsPool result{};

    std::transform(
        types.cbegin(), types.cend(), std::inserter(result, result.end()), [](const auto &type) {
            return std::make_pair(FuzzingOperationFactory::create(type.first), type.second);
        });

    return result;
}

/**
 * Class to run random tests
 */
class FuzzingTest {
public:
    explicit FuzzingTest(VariableController &variableController, Properties properties)
            : m_VariableController{variableController},
              m_Properties{std::move(properties)},
              m_VariablesPool{}
    {
        // Inits variables pool: at init, all variables are null
        for (auto variableId = 0; variableId < nbMaxVariables(); ++variableId) {
            m_VariablesPool[variableId] = nullptr;
        }
    }

    void execute()
    {
        qCInfo(LOG_TestAmdaFuzzing()) << "Running" << nbMaxOperations() << "operations on"
                                      << nbMaxVariables() << "variable(s)...";

        auto canExecute = true;
        for (auto i = 0; i < nbMaxOperations() && canExecute; ++i) {
            // Retrieves all operations that can be executed in the current context
            VariablesOperations variableOperations{};
            Weights weights{};
            std::tie(variableOperations, weights)
                = availableOperations(m_VariablesPool, operationsPool());

            canExecute = !variableOperations.empty();
            if (canExecute) {
                // Of the operations available, chooses a random operation and executes it
                auto variableOperation
                    = RandomGenerator::instance().randomChoice(variableOperations, weights);

                auto variableId = variableOperation.first;
                auto variable = m_VariablesPool.at(variableId);
                auto fuzzingOperation = variableOperation.second;

                fuzzingOperation->execute(variable, m_VariableController, m_Properties);
                QTest::qWait(operationDelay());

                // Updates variable pool with the new state of the variable after operation
                m_VariablesPool[variableId] = variable;
            }
            else {
                qCInfo(LOG_TestAmdaFuzzing())
                    << "No more operations are available, the execution of the test will stop...";
            }
        }

        qCInfo(LOG_TestAmdaFuzzing()) << "Execution of the test completed.";
    }

private:
    int nbMaxOperations() const
    {
        static auto result
            = m_Properties.value(NB_MAX_OPERATIONS_PROPERTY, NB_MAX_OPERATIONS_DEFAULT_VALUE)
                  .toInt();
        return result;
    }

    int nbMaxVariables() const
    {
        static auto result
            = m_Properties.value(NB_MAX_VARIABLES_PROPERTY, NB_MAX_VARIABLES_DEFAULT_VALUE).toInt();
        return result;
    }

    int operationDelay() const
    {
        static auto result
            = m_Properties.value(OPERATION_DELAY_PROPERTY, OPERATION_DELAY_DEFAULT_VALUE).toInt();
        return result;
    }

    WeightedOperationsPool operationsPool() const
    {
        static auto result = createOperationsPool(
            m_Properties.value(AVAILABLE_OPERATIONS_PROPERTY, AVAILABLE_OPERATIONS_DEFAULT_VALUE)
                .value<WeightedOperationsTypes>());
        return result;
    }

    VariableController &m_VariableController;
    Properties m_Properties;
    VariablesPool m_VariablesPool;
};

} // namespace

class TestAmdaFuzzing : public QObject {
    Q_OBJECT

private slots:
    /// Input data for @sa testFuzzing()
    void testFuzzing_data();
    void testFuzzing();
};

void TestAmdaFuzzing::testFuzzing_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<Properties>("properties"); // Properties for random test

    // ////////// //
    // Test cases //
    // ////////// //

    auto maxRange = SqpRange::fromDateTime({2017, 1, 1}, {0, 0}, {2017, 1, 5}, {0, 0});
    MetadataPool metadataPool{{{"dataType", "vector"}, {"xml:id", "imf"}}};

    // Note: we don't use auto here as we want to pass std::shared_ptr<IDataProvider> as is in the
    // QVariant
    std::shared_ptr<IDataProvider> provider = std::make_shared<AmdaProvider>();

    QTest::newRow("fuzzingTest") << Properties{
        {MAX_RANGE_PROPERTY, QVariant::fromValue(maxRange)},
        {METADATA_POOL_PROPERTY, QVariant::fromValue(metadataPool)},
        {PROVIDER_PROPERTY, QVariant::fromValue(provider)}};
}

void TestAmdaFuzzing::testFuzzing()
{
    QFETCH(Properties, properties);

    auto &variableController = sqpApp->variableController();
    auto &timeController = sqpApp->timeController();

    // Generates random initial range (bounded to max range)
    auto maxRange = properties.value(MAX_RANGE_PROPERTY, QVariant::fromValue(INVALID_RANGE))
                        .value<SqpRange>();

    QVERIFY(maxRange != INVALID_RANGE);

    auto initialRangeStart
        = RandomGenerator::instance().generateDouble(maxRange.m_TStart, maxRange.m_TEnd);
    auto initialRangeEnd
        = RandomGenerator::instance().generateDouble(maxRange.m_TStart, maxRange.m_TEnd);
    if (initialRangeStart > initialRangeEnd) {
        std::swap(initialRangeStart, initialRangeEnd);
    }

    // Sets initial range on time controller
    SqpRange initialRange{initialRangeStart, initialRangeEnd};
    qCInfo(LOG_TestAmdaFuzzing()) << "Setting initial range to" << initialRange << "...";
    timeController.onTimeToUpdate(initialRange);

    FuzzingTest test{variableController, properties};
    test.execute();
}

int main(int argc, char *argv[])
{
    QLoggingCategory::setFilterRules(
        "*.warning=false\n"
        "*.info=false\n"
        "*.debug=false\n"
        "FuzzingOperations.info=true\n"
        "TestAmdaFuzzing.info=true\n");

    SqpApplication app{argc, argv};
    app.setAttribute(Qt::AA_Use96Dpi, true);
    TestAmdaFuzzing testObject{};
    QTEST_SET_MAIN_SOURCE_PATH
    return QTest::qExec(&testObject, argc, argv);
}

#include "TestAmdaFuzzing.moc"
