#include <QObject>
#include <QtTest>

#include <Data/IDataProvider.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <memory>

namespace {

/// Provider used for the tests
class TestProvider : public IDataProvider {
    std::shared_ptr<IDataProvider> clone() const { return std::make_shared<TestProvider>(); }

    void requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters) override
    {
        // Does nothing
    }

    void requestDataAborting(QUuid acqIdentifier) override
    {
        // Does nothing
    }
};

/// Generates a time controller for the tests
std::unique_ptr<TimeController> defaultTimeController()
{
    auto timeController = std::make_unique<TimeController>();

    QDateTime start{QDate{2017, 01, 01}, QTime{0, 0, 0, 0}};
    QDateTime end{QDate{2017, 01, 02}, QTime{0, 0, 0, 0}};
    timeController->setDateTimeRange(
        DateTimeRange{DateUtils::secondsSinceEpoch(start), DateUtils::secondsSinceEpoch(end)});

    return timeController;
}

} // namespace

class TestVariableController : public QObject {
    Q_OBJECT

private slots:
    /// Test removes variable from controller
    void testDeleteVariable();
};

void TestVariableController::testDeleteVariable()
{
    // Creates variable controller
    auto timeController = defaultTimeController();
    VariableController variableController{};
    //variableController.setTimeController(timeController.get());

    // Creates a variable from the controller
    auto variable
        = variableController.createVariable("variable", {}, std::make_shared<TestProvider>(), timeController->dateTime());

    qDebug() << QString::number(variable.use_count());

    // Removes the variable from the controller
    variableController.deleteVariable(variable);

    // Verifies that the variable has been deleted: this implies that the number of shared_ptr
    // objects referring to the variable is 1 (the reference of this scope). Otherwise, the deletion
    // is considered invalid since the variable is still referenced in the controller
    QVERIFY(variable.use_count() == 1);
}

QTEST_MAIN(TestVariableController)
#include "TestVariableController.moc"
