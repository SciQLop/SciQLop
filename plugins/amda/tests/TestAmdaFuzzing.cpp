#include "FuzzingDefs.h"
#include "FuzzingOperations.h"
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

using OperationsPool = std::set<std::shared_ptr<IFuzzingOperation> >;
using VariablesPool = std::map<VariableId, std::shared_ptr<Variable> >;

// ///////// //
// Constants //
// ///////// //

// Defaults values used when the associated properties have not been set for the test
const auto NB_MAX_OPERATIONS_DEFAULT_VALUE = 100;
const auto NB_MAX_VARIABLES_DEFAULT_VALUE = 1;
const auto AVAILABLE_OPERATIONS_DEFAULT_VALUE
    = QVariant::fromValue(OperationsTypes{FuzzingOperationType::CREATE});
OperationsPool createOperationsPool(const OperationsTypes &types)
{
    OperationsPool result{};

    std::transform(types.cbegin(), types.cend(), std::inserter(result, result.end()),
                   [](const auto &type) { return FuzzingOperationFactory::create(type); });

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
        /// @todo: complete
        qCInfo(LOG_TestAmdaFuzzing()) << "Running" << nbMaxOperations() << "operations on"
                                      << nbMaxVariables() << "variables...";

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

    OperationsPool operationsPool() const
    {
        static auto result = createOperationsPool(
            m_Properties.value(AVAILABLE_OPERATIONS_PROPERTY, AVAILABLE_OPERATIONS_DEFAULT_VALUE)
                .value<OperationsTypes>());
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

    ///@todo: complete
}

void TestAmdaFuzzing::testFuzzing()
{
    QFETCH(Properties, properties);

    auto &variableController = sqpApp->variableController();
    auto &timeController = sqpApp->timeController();

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
