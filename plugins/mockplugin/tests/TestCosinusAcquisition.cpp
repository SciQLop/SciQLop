#include "CosinusProvider.h"

#include <SqpApplication.h>

#include <QObject>
#include <QtTest>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH = QFileInfo{
    QString{MOCKPLUGIN_TESTS_RESOURCES_DIR},
    "TestCosinusAcquisition"}.absoluteFilePath();

} // namespace

/**
 * @brief The TestCosinusAcquisition class tests acquisition in SciQlop (operations like zooms in,
 * zooms out, pans) of data from CosinusProvider
 * @sa CosinusProvider
 */
class TestCosinusAcquisition : public QObject {
    Q_OBJECT

private slots:
    /// Input data for @sa testAcquisition()
    void testAcquisition_data();
    void testAcquisition();
};

void TestCosinusAcquisition::testAcquisition_data()
{
    /// @todo
}

void TestCosinusAcquisition::testAcquisition()
{
    /// @todo
}

int main(int argc, char *argv[])
{
    SqpApplication app{argc, argv};
    app.setAttribute(Qt::AA_Use96Dpi, true);
    TestCosinusAcquisition testObject{};
    QTEST_SET_MAIN_SOURCE_PATH
    return QTest::qExec(&testObject, argc, argv);
}

#include "TestCosinusAcquisition.moc"
