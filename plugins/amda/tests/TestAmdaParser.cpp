#include "AmdaParser.h"

#include <DataSource/DataSourceItem.h>

#include <QObject>
#include <QtTest>

#include <QString>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaParser"}.absoluteFilePath();

QString inputFilePath(const QString &inputFileName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, inputFileName}.absoluteFilePath();
}

struct ExpectedResults {
    explicit ExpectedResults() = default;
    explicit ExpectedResults(std::shared_ptr<DataSourceItem> item)
            : m_ParsingOK{true}, m_Item{std::move(item)}
    {
    }

    // Parsing was successfully completed
    bool m_ParsingOK{false};
    // Expected item after parsing
    std::shared_ptr<DataSourceItem> m_Item{nullptr};
};

// ///////////////////////////////// //
// Set of expected results for tests //
// ///////////////////////////////// //

ExpectedResults validResults1()
{
    auto component1 = std::make_unique<DataSourceItem>(
        DataSourceItemType::COMPONENT,
        QHash<QString, QVariant>{{"name", "Bx"}, {"xml:id", "ice_b_cse(0)"}});
    auto component2 = std::make_unique<DataSourceItem>(
        DataSourceItemType::COMPONENT,
        QHash<QString, QVariant>{{"name", "By"}, {"xml:id", "ice_b_cse(1)"}});
    auto component3 = std::make_unique<DataSourceItem>(
        DataSourceItemType::COMPONENT,
        QHash<QString, QVariant>{{"name", "Bz"}, {"xml:id", "ice_b_cse(2)"}});
    auto parameter1 = std::make_unique<DataSourceItem>(
        DataSourceItemType::PRODUCT,
        QHash<QString, QVariant>{
            {"name", "B_cse"}, {"units", "nT"}, {"display_type", ""}, {"xml:id", "ice_b_cse"}});
    parameter1->appendChild(std::move(component1));
    parameter1->appendChild(std::move(component2));
    parameter1->appendChild(std::move(component3));

    auto parameter2 = std::make_unique<DataSourceItem>(
        DataSourceItemType::PRODUCT,
        QHash<QString, QVariant>{
            {"name", "|B|"}, {"units", "nT"}, {"display_type", ""}, {"xml:id", "ice_b_tot"}});

    auto dataset = std::make_unique<DataSourceItem>(
        DataSourceItemType::NODE, QHash<QString, QVariant>{{"att", ""},
                                                           {"restricted", ""},
                                                           {"name", "Magnetic Field"},
                                                           {"xml:id", "ice:mag:p21"},
                                                           {"sampling", "0.3s"},
                                                           {"maxSampling", ""},
                                                           {"dataStart", "1985/09/10"},
                                                           {"dataStop", "1985/09/14"},
                                                           {"dataSource", "PDS"},
                                                           {"target", ""}});
    dataset->appendChild(std::move(parameter1));
    dataset->appendChild(std::move(parameter2));

    auto instrument = std::make_unique<DataSourceItem>(
        DataSourceItemType::NODE, QHash<QString, QVariant>{{"att", ""},
                                                           {"name", "MAG"},
                                                           {"xml:id", "ICE@Giacobini-Zinner:MAG"},
                                                           {"desc", "Vector Helium Magnetometer"},
                                                           {"restricted", ""}});
    instrument->appendChild(std::move(dataset));

    auto mission = std::make_unique<DataSourceItem>(
        DataSourceItemType::NODE,
        QHash<QString, QVariant>{{"att", ""},
                                 {"name", "ICE@Giacobini-Zinner"},
                                 {"rank", "93"},
                                 {"xml:id", "ICE@Giacobini-Zinner"},
                                 {"desc", "International Cometary Explorer"},
                                 {"target", "Comet"},
                                 {"available", "1"}});
    mission->appendChild(std::move(instrument));

    auto item = std::make_shared<DataSourceItem>(DataSourceItemType::NODE,
                                                 QHash<QString, QVariant>{
                                                     {"name", "AMDA"},
                                                     {"desc", "AMDA_Internal_Data_Base"},
                                                     {"xml:id", "myLocalData-treeRootNode"},
                                                 });
    item->appendChild(std::move(mission));

    return ExpectedResults{item};
}

ExpectedResults invalidResults()
{
    return ExpectedResults{};
}

} // namespace

Q_DECLARE_METATYPE(ExpectedResults)

class TestAmdaParser : public QObject {
    Q_OBJECT
private slots:
    /// Input test data
    /// @sa testReadJson()
    void testReadJson_data();

    /// Tests parsing of a JSON file
    void testReadJson();
};

void TestAmdaParser::testReadJson_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Name of JSON file to read
    QTest::addColumn<QString>("inputFileName");
    // Expected results
    QTest::addColumn<ExpectedResults>("expectedResults");

    // ////////// //
    // Test cases //
    // ////////// //

    // Valid file
    QTest::newRow("Valid file") << QStringLiteral("ValidFile1.json") << validResults1();

    // Invalid files
    QTest::newRow("Invalid file (unexisting file)") << QStringLiteral("UnexistingFile.json")
                                                    << invalidResults();
    QTest::newRow("Invalid file (two root objects)") << QStringLiteral("TwoRootsFile.json")
                                                     << invalidResults();
    QTest::newRow("Invalid file (wrong root key)") << QStringLiteral("WrongRootKey.json")
                                                   << invalidResults();
    QTest::newRow("Invalid file (wrong root type)") << QStringLiteral("WrongRootType.json")
                                                    << invalidResults();
}

void TestAmdaParser::testReadJson()
{
    QFETCH(QString, inputFileName);
    QFETCH(ExpectedResults, expectedResults);

    // Parses file
    auto filePath = inputFilePath(inputFileName);
    auto item = AmdaParser::readJson(filePath);

    // Validates results
    if (expectedResults.m_ParsingOK) {
        QVERIFY(item != nullptr);
        QVERIFY(expectedResults.m_Item != nullptr);
        QVERIFY(*item == *expectedResults.m_Item);
    }
    else {
        QVERIFY(item == nullptr);
    }
}

QTEST_MAIN(TestAmdaParser)
#include "TestAmdaParser.moc"
