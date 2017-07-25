#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>

#include <QObject>
#include <QtTest>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaResultParser"}.absoluteFilePath();

QString inputFilePath(const QString &inputFileName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, inputFileName}.absoluteFilePath();
}

struct ExpectedResults {
    explicit ExpectedResults() = default;

    /// Ctor with QVector<QDateTime> as x-axis data. Datetimes are converted to doubles
    explicit ExpectedResults(Unit xAxisUnit, Unit valuesUnit, const QVector<QDateTime> &xAxisData,
                             QVector<double> valuesData)
            : m_ParsingOK{true},
              m_XAxisUnit{xAxisUnit},
              m_ValuesUnit{valuesUnit},
              m_XAxisData{},
              m_ValuesData{std::move(valuesData)}
    {
        // Converts QVector<QDateTime> to QVector<double>
        std::transform(xAxisData.cbegin(), xAxisData.cend(), std::back_inserter(m_XAxisData),
                       [](const auto &dateTime) { return dateTime.toMSecsSinceEpoch() / 1000.; });
    }

    /**
     * Validates a DataSeries compared to the expected results
     * @param results the DataSeries to validate
     */
    void validate(std::shared_ptr<IDataSeries> results)
    {
        if (m_ParsingOK) {
            auto scalarSeries = dynamic_cast<ScalarSeries *>(results.get());
            QVERIFY(scalarSeries != nullptr);

            // Checks units
            QVERIFY(scalarSeries->xAxisUnit() == m_XAxisUnit);
            QVERIFY(scalarSeries->valuesUnit() == m_ValuesUnit);

            // Checks values
            QVERIFY(scalarSeries->xAxisData()->data() == m_XAxisData);
            QVERIFY(scalarSeries->valuesData()->data() == m_ValuesData);
        }
        else {
            QVERIFY(results == nullptr);
        }
    }

    // Parsing was successfully completed
    bool m_ParsingOK{false};
    // Expected x-axis unit
    Unit m_XAxisUnit{};
    // Expected values unit
    Unit m_ValuesUnit{};
    // Expected x-axis data
    QVector<double> m_XAxisData{};
    // Expected values data
    QVector<double> m_ValuesData{};
};

} // namespace

Q_DECLARE_METATYPE(ExpectedResults)

class TestAmdaResultParser : public QObject {
    Q_OBJECT
private slots:
    /// Input test data
    /// @sa testTxtJson()
    void testReadTxt_data();

    /// Tests parsing of a TXT file
    void testReadTxt();
};

void TestAmdaResultParser::testReadTxt_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    // Name of TXT file to read
    QTest::addColumn<QString>("inputFileName");
    // Expected results
    QTest::addColumn<ExpectedResults>("expectedResults");

    // ////////// //
    // Test cases //
    // ////////// //

    auto dateTime = [](int year, int month, int day, int hours, int minutes, int seconds) {
        return QDateTime{{year, month, day}, {hours, minutes, seconds}};
    };

    // Valid file
    QTest::newRow("Valid file")
        << QStringLiteral("ValidScalar1.txt")
        << ExpectedResults{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                                  dateTime(2013, 9, 23, 9, 2, 30), dateTime(2013, 9, 23, 9, 3, 30),
                                  dateTime(2013, 9, 23, 9, 4, 30), dateTime(2013, 9, 23, 9, 5, 30),
                                  dateTime(2013, 9, 23, 9, 6, 30), dateTime(2013, 9, 23, 9, 7, 30),
                                  dateTime(2013, 9, 23, 9, 8, 30), dateTime(2013, 9, 23, 9, 9, 30)},
               QVector<double>{-2.83950, -2.71850, -2.52150, -2.57633, -2.58050, -2.48325, -2.63025,
                               -2.55800, -2.43250, -2.42200}};

    // Valid files but with some invalid lines (wrong unit, wrong values, etc.)
    QTest::newRow("No unit file") << QStringLiteral("NoUnit.txt")
                                  << ExpectedResults{Unit{QStringLiteral(""), true}, Unit{},
                                                     QVector<QDateTime>{}, QVector<double>{}};
    QTest::newRow("Wrong unit file")
        << QStringLiteral("WrongUnit.txt")
        << ExpectedResults{Unit{QStringLiteral(""), true}, Unit{},
                           QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30),
                                              dateTime(2013, 9, 23, 9, 1, 30),
                                              dateTime(2013, 9, 23, 9, 2, 30)},
                           QVector<double>{-2.83950, -2.71850, -2.52150}};

    QTest::newRow("Wrong results file (date of first line is invalid")
        << QStringLiteral("WrongDate.txt")
        << ExpectedResults{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Wrong results file (too many values for first line")
        << QStringLiteral("TooManyValues.txt")
        << ExpectedResults{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Wrong results file (value of first line is invalid")
        << QStringLiteral("WrongValue.txt")
        << ExpectedResults{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Wrong results file (value of first line is NaN")
        << QStringLiteral("NaNValue.txt")
        << ExpectedResults{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    // Invalid files
    QTest::newRow("Invalid file (unexisting file)")
        << QStringLiteral("UnexistingFile.txt") << ExpectedResults{};

    QTest::newRow("Invalid file (file not found on server)")
        << QStringLiteral("FileNotFound.txt") << ExpectedResults{};
}

void TestAmdaResultParser::testReadTxt()
{
    QFETCH(QString, inputFileName);
    QFETCH(ExpectedResults, expectedResults);

    // Parses file
    auto filePath = inputFilePath(inputFileName);
    auto results = AmdaResultParser::readTxt(filePath);

    // ///////////////// //
    // Validates results //
    // ///////////////// //
    expectedResults.validate(results);
}

QTEST_MAIN(TestAmdaResultParser)
#include "TestAmdaResultParser.moc"
