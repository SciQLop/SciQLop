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

/**
 * Class to run random tests
 */
class FuzzingTest {
public:
    void execute()
    {
        /// @todo: complete
        qCInfo(LOG_TestAmdaFuzzing()) << "Execution of the test completed.";
    }
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

    /// @todo: complete

    // ////////// //
    // Test cases //
    // ////////// //

    ///@todo: complete
}

void TestAmdaFuzzing::testFuzzing()
{
    auto &variableController = sqpApp->variableController();
    auto &timeController = sqpApp->timeController();

    FuzzingTest test{};
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
