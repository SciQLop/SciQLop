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
