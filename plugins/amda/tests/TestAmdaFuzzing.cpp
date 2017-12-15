#include "FuzzingDefs.h"
#include "FuzzingOperations.h"
#include "FuzzingUtils.h"
#include "FuzzingValidators.h"

#include "AmdaProvider.h"

#include <Common/SignalWaiter.h>
#include <Network/NetworkController.h>
#include <Settings/SqpSettingsDefs.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <QLoggingCategory>
#include <QObject>
#include <QtTest>

#include <memory>

Q_LOGGING_CATEGORY(LOG_TestAmdaFuzzing, "TestAmdaFuzzing")

/**
 * Macro used to generate a getter for a property in @sa FuzzingTest. The macro generates a static
 * attribute that is initialized by searching in properties the property and use a default value if
 * it's not present. Macro arguments are:
 * - GETTER_NAME : name of the getter
 * - PROPERTY_NAME: used to generate constants for property's name ({PROPERTY_NAME}_PROPERTY) and
 * default value ({PROPERTY_NAME}_DEFAULT_VALUE)
 * - TYPE : return type of the getter
 */
// clang-format off
#define DECLARE_PROPERTY_GETTER(GETTER_NAME, PROPERTY_NAME, TYPE)  \
TYPE GETTER_NAME() const \
{ \
    static auto result = m_Properties.value(PROPERTY_NAME##_PROPERTY, PROPERTY_NAME##_DEFAULT_VALUE).value<TYPE>(); \
    return result; \
} \
// clang-format on

namespace {

// /////// //
// Aliases //
// /////// //

using IntPair = std::pair<int, int>;
using Weight = double;
using Weights = std::vector<Weight>;

struct OperationProperty {
    Weight m_Weight{1.};
    bool m_WaitAcquisition{false};
};

using VariableOperation = std::pair<VariableId, std::shared_ptr<IFuzzingOperation> >;
using VariablesOperations = std::vector<VariableOperation>;

using OperationsTypes = std::map<FuzzingOperationType, OperationProperty>;
using OperationsPool = std::map<std::shared_ptr<IFuzzingOperation>, OperationProperty>;

using Validators = std::vector<std::shared_ptr<IFuzzingValidator> >;

// ///////// //
// Constants //
// ///////// //

// Defaults values used when the associated properties have not been set for the test
const auto ACQUISITION_TIMEOUT_DEFAULT_VALUE = 30000;
const auto NB_MAX_OPERATIONS_DEFAULT_VALUE = 100;
const auto NB_MAX_SYNC_GROUPS_DEFAULT_VALUE = 1;
const auto NB_MAX_VARIABLES_DEFAULT_VALUE = 1;
const auto AVAILABLE_OPERATIONS_DEFAULT_VALUE = QVariant::fromValue(WeightedOperationsTypes{
    {FuzzingOperationType::CREATE, 1.},
    {FuzzingOperationType::DELETE, 0.1}, // Delete operation is less frequent
    {FuzzingOperationType::PAN_LEFT, 1.},
    {FuzzingOperationType::PAN_RIGHT, 1.},
    {FuzzingOperationType::ZOOM_IN, 1.},
    {FuzzingOperationType::ZOOM_OUT, 1.},
    {FuzzingOperationType::SYNCHRONIZE, 0.8},
    {FuzzingOperationType::DESYNCHRONIZE, 0.4}});
const auto CACHE_TOLERANCE_DEFAULT_VALUE = 0.2;

/// Min/max delays between each operation (in ms)
const auto OPERATION_DELAY_BOUNDS_DEFAULT_VALUE = QVariant::fromValue(std::make_pair(100, 3000));

/// Validators for the tests (executed in the order in which they're defined)
const auto VALIDATORS_DEFAULT_VALUE = QVariant::fromValue(
    ValidatorsTypes{{FuzzingValidatorType::RANGE, FuzzingValidatorType::DATA}});

/// Min/max number of operations to execute before calling validation
const auto VALIDATION_FREQUENCY_BOUNDS_DEFAULT_VALUE = QVariant::fromValue(std::make_pair(1, 10));

// /////// //
// Methods //
// /////// //

/// Goes through the variables pool and operations pool to determine the set of {variable/operation}
/// pairs that are valid (i.e. operation that can be executed on variable)
std::pair<VariablesOperations, Weights> availableOperations(const FuzzingState &fuzzingState,
                                                            const OperationsPool &operationsPool)
{
    VariablesOperations result{};
    Weights weights{};

    for (const auto &variablesPoolEntry : fuzzingState.m_VariablesPool) {
        auto variableId = variablesPoolEntry.first;

        for (const auto &operationsPoolEntry : operationsPool) {
            auto operation = operationsPoolEntry.first;
            auto operationProperty = operationsPoolEntry.second;

            // A pair is valid if the current operation can be executed on the current variable
            if (operation->canExecute(variableId, fuzzingState)) {
                result.push_back({variableId, operation});
                weights.push_back(operationProperty.m_Weight);
            }
        }
    }

    return {result, weights};
}

OperationsPool createOperationsPool(const OperationsTypes &types)
{
    OperationsPool result{};

    std::transform(
        types.cbegin(), types.cend(), std::inserter(result, result.end()), [](const auto &type) {
            return std::make_pair(FuzzingOperationFactory::create(type.first), type.second);
        });

    return result;
}

Validators createValidators(const ValidatorsTypes &types)
{
    Validators result{};

    std::transform(types.cbegin(), types.cend(), std::inserter(result, result.end()),
                   [](const auto &type) { return FuzzingValidatorFactory::create(type); });

    return result;
}

/**
 * Validates all the variables' states passed in parameter, according to a set of validators
 * @param variablesPool the variables' states
 * @param validators the validators used for validation
 */
void validate(const VariablesPool &variablesPool, const Validators &validators)
{
    for (const auto &variablesPoolEntry : variablesPool) {
        auto variableId = variablesPoolEntry.first;
        const auto &variableState = variablesPoolEntry.second;

        auto variableMessage = variableState.m_Variable ? variableState.m_Variable->name()
                                                        : QStringLiteral("null variable");
        qCInfo(LOG_TestAmdaFuzzing()).noquote() << "Validating state of variable at index"
                                                << variableId << "(" << variableMessage << ")...";

        for (const auto &validator : validators) {
            validator->validate(VariableState{variableState});
        }

        qCInfo(LOG_TestAmdaFuzzing()).noquote() << "Validation completed.";
    }
}

/**
 * Class to run random tests
 */
class FuzzingTest {
public:
    explicit FuzzingTest(VariableController &variableController, Properties properties)
            : m_VariableController{variableController},
              m_Properties{std::move(properties)},
              m_FuzzingState{}
    {
        // Inits variables pool: at init, all variables are null
        for (auto variableId = 0; variableId < nbMaxVariables(); ++variableId) {
            m_FuzzingState.m_VariablesPool[variableId] = VariableState{};
        }

        // Inits sync groups and registers them into the variable controller
        for (auto i = 0; i < nbMaxSyncGroups(); ++i) {
            auto syncGroupId = SyncGroupId::createUuid();
            variableController.onAddSynchronizationGroupId(syncGroupId);
            m_FuzzingState.m_SyncGroupsPool[syncGroupId] = SyncGroup{};
        }
    }

    void execute()
    {
        qCInfo(LOG_TestAmdaFuzzing()).noquote() << "Running" << nbMaxOperations() << "operations on"
                                                << nbMaxVariables() << "variable(s)...";


        // Inits the count of the number of operations before the next validation
        int nextValidationCounter = 0;
        auto updateValidationCounter = [this, &nextValidationCounter]() {
            nextValidationCounter = RandomGenerator::instance().generateInt(
                validationFrequencies().first, validationFrequencies().second);
            qCInfo(LOG_TestAmdaFuzzing()).noquote()
                << "Next validation in " << nextValidationCounter << "operation(s)...";
        };
        updateValidationCounter();

        auto canExecute = true;
        for (auto i = 0; i < nbMaxOperations() && canExecute; ++i) {
            // Retrieves all operations that can be executed in the current context
            VariablesOperations variableOperations{};
            Weights weights{};
            std::tie(variableOperations, weights)
                = availableOperations(m_FuzzingState, operationsPool());

            canExecute = !variableOperations.empty();
            if (canExecute) {
                --nextValidationCounter;

                // Of the operations available, chooses a random operation and executes it
                auto variableOperation
                    = RandomGenerator::instance().randomChoice(variableOperations, weights);

                auto variableId = variableOperation.first;
                auto fuzzingOperation = variableOperation.second;

                auto waitAcquisition = nextValidationCounter == 0;

                fuzzingOperation->execute(variableId, m_FuzzingState, m_VariableController,
                                          m_Properties);

                if (waitAcquisition) {
                    qCDebug(LOG_TestAmdaFuzzing()) << "Waiting for acquisition to finish...";
                    SignalWaiter{m_VariableController, SIGNAL(acquisitionFinished())}.wait(
                        acquisitionTimeout());

                    // Validates variables
                    validate(m_FuzzingState.m_VariablesPool, validators());
                    updateValidationCounter();
                }
                else {
                    // Delays the next operation with a randomly generated time
                    auto delay = RandomGenerator::instance().generateInt(operationDelays().first,
                                                                         operationDelays().second);
                    qCDebug(LOG_TestAmdaFuzzing())
                        << "Waiting " << delay << "ms before the next operation...";
                    QTest::qWait(delay);
                }
            }
            else {
                qCInfo(LOG_TestAmdaFuzzing()).noquote()
                    << "No more operations are available, the execution of the test will stop...";
            }
        }

        qCInfo(LOG_TestAmdaFuzzing()).noquote() << "Execution of the test completed.";
    }

private:
    OperationsPool operationsPool() const
    {
        static auto result = createOperationsPool(
            m_Properties.value(AVAILABLE_OPERATIONS_PROPERTY, AVAILABLE_OPERATIONS_DEFAULT_VALUE)
                .value<OperationsTypes>());
        return result;
    }

    Validators validators() const
    {
        static auto result
            = createValidators(m_Properties.value(VALIDATORS_PROPERTY, VALIDATORS_DEFAULT_VALUE)
                                   .value<ValidatorsTypes>());
        return result;
    }

    DECLARE_PROPERTY_GETTER(nbMaxOperations, NB_MAX_OPERATIONS, int)
    DECLARE_PROPERTY_GETTER(nbMaxSyncGroups, NB_MAX_SYNC_GROUPS, int)
    DECLARE_PROPERTY_GETTER(nbMaxVariables, NB_MAX_VARIABLES, int)
    DECLARE_PROPERTY_GETTER(operationDelays, OPERATION_DELAY_BOUNDS, IntPair)
    DECLARE_PROPERTY_GETTER(validationFrequencies, VALIDATION_FREQUENCY_BOUNDS, IntPair)
    DECLARE_PROPERTY_GETTER(acquisitionTimeout, ACQUISITION_TIMEOUT, int)

    VariableController &m_VariableController;
    Properties m_Properties;
    FuzzingState m_FuzzingState;
};

} // namespace

Q_DECLARE_METATYPE(OperationsTypes)

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

    // Sets cache property
    QSettings settings{};
    auto cacheTolerance = properties.value(CACHE_TOLERANCE_PROPERTY, CACHE_TOLERANCE_DEFAULT_VALUE);
    settings.setValue(GENERAL_TOLERANCE_AT_INIT_KEY, cacheTolerance);
    settings.setValue(GENERAL_TOLERANCE_AT_UPDATE_KEY, cacheTolerance);

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
    qCInfo(LOG_TestAmdaFuzzing()).noquote() << "Setting initial range to" << initialRange << "...";
    timeController.onTimeToUpdate(initialRange);
    properties.insert(INITIAL_RANGE_PROPERTY, QVariant::fromValue(initialRange));

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
        "FuzzingValidators.info=true\n"
        "TestAmdaFuzzing.info=true\n");

    SqpApplication app{argc, argv};
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop-TestFuzzing");
    app.setAttribute(Qt::AA_Use96Dpi, true);
    TestAmdaFuzzing testObject{};
    QTEST_SET_MAIN_SOURCE_PATH
    return QTest::qExec(&testObject, argc, argv);
}

#include "TestAmdaFuzzing.moc"
