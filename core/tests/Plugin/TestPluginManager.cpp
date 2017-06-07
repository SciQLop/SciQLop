#include <Plugin/PluginManager.h>

#include <QObject>
#include <QtTest>

#include <QtDebug>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH = QFileInfo{
    QString{SCQCORE_TESTS_RESOURCES_PATH},
    "Plugin/TestPluginManager"}.absoluteFilePath();

QString pluginDirPath(const QString &pluginDirName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, pluginDirName}.absoluteFilePath();
}

} // namespace

class TestPluginManager : public QObject {
    Q_OBJECT
private slots:
    /// Defines data for plugin loading
    /// @sa testLoadPlugin()
    void testLoadPlugin_data();

    /// Tests plugin loading
    void testLoadPlugin();
};

void TestPluginManager::testLoadPlugin_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Name of directory containing the plugins
    QTest::addColumn<QString>("pluginDirName");
    // Number of loaded plugins expected
    QTest::addColumn<int>("nbPluginsLoaded");

    // ////////// //
    // Test cases //
    // ////////// //

    QTest::newRow("Valid plugin") << QStringLiteral("Test_ValidPlugin") << 1;

    // Two different plugins
    QTest::newRow("Valid plugins") << QStringLiteral("Test_ValidPlugins") << 2;

    // Two plugins with the same name: we expect that only one is loaded
    QTest::newRow("Duplicated plugins") << QStringLiteral("Test_DuplicatedPlugins") << 1;

    QTest::newRow("Invalid plugin (not a DLL)") << QStringLiteral("Test_InvalidFileType") << 0;
    QTest::newRow("Invalid plugin (not a SciQlop DLL)")
        << QStringLiteral("Test_NotSciqlopDll") << 0;
    QTest::newRow("Invalid plugin (missing metadata)")
        << QStringLiteral("Test_MissingPluginMetadata") << 0;
}

void TestPluginManager::testLoadPlugin()
{
    QFETCH(QString, pluginDirName);
    QFETCH(int, nbPluginsLoaded);

    // Generates plugin dir
    auto pluginDir = QDir{pluginDirPath(pluginDirName)};
    QVERIFY(pluginDir.exists());

    // Load plugins
    PluginManager pluginManager{};
    pluginManager.loadPlugins(pluginDir);

    // Check the number of plugins loaded
    QCOMPARE(pluginManager.nbPluginsLoaded(), nbPluginsLoaded);
}

QTEST_MAIN(TestPluginManager)
#include "TestPluginManager.moc"
