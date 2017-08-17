#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>
#include <Data/VectorSeries.h>

#include <QObject>
#include <QtTest>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaResultParser"}.absoluteFilePath();

QDateTime dateTime(int year, int month, int day, int hours, int minutes, int seconds)
{
    return QDateTime{{year, month, day}, {hours, minutes, seconds}, Qt::UTC};
}

/// Compares two vectors that can potentially contain NaN values
bool compareVectors(const QVector<double> &v1, const QVector<double> &v2)
{
    if (v1.size() != v2.size()) {
        return false;
    }

    auto result = true;
    auto v2It = v2.cbegin();
    for (auto v1It = v1.cbegin(), v1End = v1.cend(); v1It != v1End && result; ++v1It, ++v2It) {
        auto v1Value = *v1It;
        auto v2Value = *v2It;

        // If v1 is NaN, v2 has to be NaN too
        result = std::isnan(v1Value) ? std::isnan(v2Value) : (v1Value == v2Value);
    }

    return result;
}

bool compareVectors(const QVector<QVector<double> > &v1, const QVector<QVector<double> > &v2)
{
    if (v1.size() != v2.size()) {
        return false;
    }

    auto result = true;
    for (auto i = 0; i < v1.size() && result; ++i) {
        result &= compareVectors(v1.at(i), v2.at(i));
    }

    return result;
}

QVector<QVector<double> > valuesData(const ArrayData<1> &arrayData)
{
    return QVector<QVector<double> >{arrayData.data()};
}

QVector<QVector<double> > valuesData(const ArrayData<2> &arrayData)
{
    return arrayData.data();
}


QString inputFilePath(const QString &inputFileName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, inputFileName}.absoluteFilePath();
}

template <typename T>
struct ExpectedResults {
    explicit ExpectedResults() = default;

    explicit ExpectedResults(Unit xAxisUnit, Unit valuesUnit, const QVector<QDateTime> &xAxisData,
                             QVector<double> valuesData)
            : ExpectedResults(xAxisUnit, valuesUnit, xAxisData,
                              QVector<QVector<double> >{std::move(valuesData)})
    {
    }

    /// Ctor with QVector<QDateTime> as x-axis data. Datetimes are converted to doubles
    explicit ExpectedResults(Unit xAxisUnit, Unit valuesUnit, const QVector<QDateTime> &xAxisData,
                             QVector<QVector<double> > valuesData)
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
            auto dataSeries = dynamic_cast<T *>(results.get());
            QVERIFY(dataSeries != nullptr);

            // Checks units
            QVERIFY(dataSeries->xAxisUnit() == m_XAxisUnit);
            QVERIFY(dataSeries->valuesUnit() == m_ValuesUnit);

            // Checks values : as the vectors can potentially contain NaN values, we must use a
            // custom vector comparison method
            QVERIFY(compareVectors(dataSeries->xAxisData()->data(), m_XAxisData));
            QVERIFY(compareVectors(valuesData(*dataSeries->valuesData()), m_ValuesData));
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
    QVector<QVector<double> > m_ValuesData{};
};

} // namespace

Q_DECLARE_METATYPE(ExpectedResults<ScalarSeries>)
Q_DECLARE_METATYPE(ExpectedResults<VectorSeries>)

class TestAmdaResultParser : public QObject {
    Q_OBJECT
private:
    template <typename T>
    void testReadDataStructure()
    {
        // ////////////// //
        // Test structure //
        // ////////////// //

        // Name of TXT file to read
        QTest::addColumn<QString>("inputFileName");
        // Expected results
        QTest::addColumn<ExpectedResults<T> >("expectedResults");
    }

    template <typename T>
    void testRead(AmdaResultParser::ValueType valueType)
    {
        QFETCH(QString, inputFileName);
        QFETCH(ExpectedResults<T>, expectedResults);

        // Parses file
        auto filePath = inputFilePath(inputFileName);
        auto results = AmdaResultParser::readTxt(filePath, valueType);

        // ///////////////// //
        // Validates results //
        // ///////////////// //
        expectedResults.validate(results);
    }

private slots:
    /// Input test data
    /// @sa testReadScalarTxt()
    void testReadScalarTxt_data();

    /// Tests parsing scalar series of a TXT file
    void testReadScalarTxt();

    /// Input test data
    /// @sa testReadVectorTxt()
    void testReadVectorTxt_data();

    /// Tests parsing vector series of a TXT file
    void testReadVectorTxt();
};

void TestAmdaResultParser::testReadScalarTxt_data()
{
    testReadDataStructure<ScalarSeries>();

    // ////////// //
    // Test cases //
    // ////////// //

    // Valid files
    QTest::newRow("Valid file")
        << QStringLiteral("ValidScalar1.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                                  dateTime(2013, 9, 23, 9, 2, 30), dateTime(2013, 9, 23, 9, 3, 30),
                                  dateTime(2013, 9, 23, 9, 4, 30), dateTime(2013, 9, 23, 9, 5, 30),
                                  dateTime(2013, 9, 23, 9, 6, 30), dateTime(2013, 9, 23, 9, 7, 30),
                                  dateTime(2013, 9, 23, 9, 8, 30), dateTime(2013, 9, 23, 9, 9, 30)},
               QVector<double>{-2.83950, -2.71850, -2.52150, -2.57633, -2.58050, -2.48325, -2.63025,
                               -2.55800, -2.43250, -2.42200}};

    QTest::newRow("Valid file (value of first line is invalid but it is converted to NaN")
        << QStringLiteral("WrongValue.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                                  dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{std::numeric_limits<double>::quiet_NaN(), -2.71850, -2.52150}};

    QTest::newRow("Valid file that contains NaN values")
        << QStringLiteral("NaNValue.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                                  dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{std::numeric_limits<double>::quiet_NaN(), -2.71850, -2.52150}};

    // Valid files but with some invalid lines (wrong unit, wrong values, etc.)
    QTest::newRow("No unit file") << QStringLiteral("NoUnit.txt")
                                  << ExpectedResults<ScalarSeries>{Unit{QStringLiteral(""), true},
                                                                   Unit{}, QVector<QDateTime>{},
                                                                   QVector<double>{}};
    QTest::newRow("Wrong unit file")
        << QStringLiteral("WrongUnit.txt")
        << ExpectedResults<ScalarSeries>{Unit{QStringLiteral(""), true}, Unit{},
                                         QVector<QDateTime>{dateTime(2013, 9, 23, 9, 0, 30),
                                                            dateTime(2013, 9, 23, 9, 1, 30),
                                                            dateTime(2013, 9, 23, 9, 2, 30)},
                                         QVector<double>{-2.83950, -2.71850, -2.52150}};

    QTest::newRow("Wrong results file (date of first line is invalid")
        << QStringLiteral("WrongDate.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Wrong results file (too many values for first line")
        << QStringLiteral("TooManyValues.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Wrong results file (x of first line is NaN")
        << QStringLiteral("NaNX.txt")
        << ExpectedResults<ScalarSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)},
               QVector<double>{-2.71850, -2.52150}};

    QTest::newRow("Invalid file type (vector)")
        << QStringLiteral("ValidVector1.txt")
        << ExpectedResults<ScalarSeries>{Unit{QStringLiteral("nT"), true}, Unit{},
                                         QVector<QDateTime>{}, QVector<double>{}};

    // Invalid files
    QTest::newRow("Invalid file (unexisting file)")
        << QStringLiteral("UnexistingFile.txt") << ExpectedResults<ScalarSeries>{};

    QTest::newRow("Invalid file (file not found on server)")
        << QStringLiteral("FileNotFound.txt") << ExpectedResults<ScalarSeries>{};
}

void TestAmdaResultParser::testReadScalarTxt()
{
    testRead<ScalarSeries>(AmdaResultParser::ValueType::SCALAR);
}

void TestAmdaResultParser::testReadVectorTxt_data()
{
    testReadDataStructure<VectorSeries>();

    // ////////// //
    // Test cases //
    // ////////// //

    // Valid files
    QTest::newRow("Valid file")
        << QStringLiteral("ValidVector1.txt")
        << ExpectedResults<VectorSeries>{
               Unit{QStringLiteral("nT"), true}, Unit{},
               QVector<QDateTime>{dateTime(2013, 7, 2, 9, 13, 50), dateTime(2013, 7, 2, 9, 14, 6),
                                  dateTime(2013, 7, 2, 9, 14, 22), dateTime(2013, 7, 2, 9, 14, 38),
                                  dateTime(2013, 7, 2, 9, 14, 54), dateTime(2013, 7, 2, 9, 15, 10),
                                  dateTime(2013, 7, 2, 9, 15, 26), dateTime(2013, 7, 2, 9, 15, 42),
                                  dateTime(2013, 7, 2, 9, 15, 58), dateTime(2013, 7, 2, 9, 16, 14)},
               QVector<QVector<double> >{
                   {-0.332, -1.011, -1.457, -1.293, -1.217, -1.443, -1.278, -1.202, -1.22, -1.259},
                   {3.206, 2.999, 2.785, 2.736, 2.612, 2.564, 2.892, 2.862, 2.859, 2.764},
                   {0.058, 0.496, 1.018, 1.485, 1.662, 1.505, 1.168, 1.244, 1.15, 1.358}}};

    // Valid files but with some invalid lines (wrong unit, wrong values, etc.)
    QTest::newRow("Invalid file type (scalar)")
        << QStringLiteral("ValidScalar1.txt")
        << ExpectedResults<VectorSeries>{Unit{QStringLiteral("nT"), true}, Unit{},
                                         QVector<QDateTime>{},
                                         QVector<QVector<double> >{{}, {}, {}}};
}

void TestAmdaResultParser::testReadVectorTxt()
{
    testRead<VectorSeries>(AmdaResultParser::ValueType::VECTOR);
}

QTEST_MAIN(TestAmdaResultParser)
#include "TestAmdaResultParser.moc"
