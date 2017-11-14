#include "AmdaResultParser.h"

#include <Data/ScalarSeries.h>
#include <Data/SpectrogramSeries.h>
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

QString inputFilePath(const QString &inputFileName)
{
    return QFileInfo{TESTS_RESOURCES_PATH, inputFileName}.absoluteFilePath();
}

template <typename T>
struct ExpectedResults {

    ExpectedResults &setParsingOK(bool parsingOK)
    {
        m_ParsingOK = parsingOK;
        return *this;
    }

    ExpectedResults &setXAxisUnit(Unit xAxisUnit)
    {
        m_XAxisUnit = std::move(xAxisUnit);
        return *this;
    }

    ExpectedResults &setXAxisData(const QVector<QDateTime> &xAxisData)
    {
        m_XAxisData.clear();

        // Converts QVector<QDateTime> to QVector<double>
        std::transform(xAxisData.cbegin(), xAxisData.cend(), std::back_inserter(m_XAxisData),
                       [](const auto &dateTime) { return dateTime.toMSecsSinceEpoch() / 1000.; });

        return *this;
    }

    ExpectedResults &setValuesUnit(Unit valuesUnit)
    {
        m_ValuesUnit = std::move(valuesUnit);
        return *this;
    }

    ExpectedResults &setValuesData(QVector<double> valuesData)
    {
        m_ValuesData.clear();
        m_ValuesData.push_back(std::move(valuesData));
        return *this;
    }

    ExpectedResults &setValuesData(QVector<QVector<double> > valuesData)
    {
        m_ValuesData = std::move(valuesData);
        return *this;
    }

    ExpectedResults &setYAxisEnabled(bool yAxisEnabled)
    {
        m_YAxisEnabled = yAxisEnabled;
        return *this;
    }

    ExpectedResults &setYAxisUnit(Unit yAxisUnit)
    {
        m_YAxisUnit = std::move(yAxisUnit);
        return *this;
    }

    ExpectedResults &setYAxisData(QVector<double> yAxisData)
    {
        m_YAxisData = std::move(yAxisData);
        return *this;
    }

    /**
     * Validates a DataSeries compared to the expected results
     * @param results the DataSeries to validate
     */
    void validate(std::shared_ptr<IDataSeries> results)
    {
        if (m_ParsingOK) {
            auto dataSeries = dynamic_cast<T *>(results.get());
            if (dataSeries == nullptr) {

                // No unit detected, parsink ok but data is nullptr
                // TODO, improve the test to verify that the data is null
                return;
            }

            // Checks units
            QVERIFY(dataSeries->xAxisUnit() == m_XAxisUnit);
            QVERIFY(dataSeries->valuesUnit() == m_ValuesUnit);

            auto verifyRange = [dataSeries](const auto &expectedData, const auto &equalFun) {
                QVERIFY(std::equal(dataSeries->cbegin(), dataSeries->cend(), expectedData.cbegin(),
                                   expectedData.cend(),
                                   [&equalFun](const auto &dataSeriesIt, const auto &expectedX) {
                                       return equalFun(dataSeriesIt, expectedX);
                                   }));
            };

            // Checks x-axis data
            verifyRange(m_XAxisData, [](const auto &seriesIt, const auto &value) {
                return seriesIt.x() == value;
            });

            // Checks values data of each component
            for (auto i = 0; i < m_ValuesData.size(); ++i) {
                verifyRange(m_ValuesData.at(i), [i](const auto &seriesIt, const auto &value) {
                    auto itValue = seriesIt.value(i);
                    return (std::isnan(itValue) && std::isnan(value)) || seriesIt.value(i) == value;
                });
            }

            // Checks y-axis (if defined)
            auto yAxis = dataSeries->yAxis();
            QCOMPARE(yAxis.isDefined(), m_YAxisEnabled);

            if (m_YAxisEnabled) {
                // Unit
                QCOMPARE(yAxis.unit(), m_YAxisUnit);

                // Data
                QVERIFY(std::equal(yAxis.cbegin(), yAxis.cend(), m_YAxisData.cbegin(),
                                   m_YAxisData.cend(), [](const auto &it, const auto &expectedVal) {
                                       return it.first() == expectedVal;
                                   }));
            }
        }
        else {
            QVERIFY(results == nullptr);
        }
    }

    // Parsing was successfully completed
    bool m_ParsingOK{false};
    // Expected x-axis unit
    Unit m_XAxisUnit{};
    // Expected x-axis data
    QVector<double> m_XAxisData{};
    // Expected values unit
    Unit m_ValuesUnit{};
    // Expected values data
    QVector<QVector<double> > m_ValuesData{};
    // Expected data series has y-axis
    bool m_YAxisEnabled{false};
    // Expected y-axis unit (if axis defined)
    Unit m_YAxisUnit{};
    // Expected y-axis data (if axis defined)
    QVector<double> m_YAxisData{};
};

} // namespace

Q_DECLARE_METATYPE(ExpectedResults<ScalarSeries>)
Q_DECLARE_METATYPE(ExpectedResults<SpectrogramSeries>)
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
    /// @sa testReadSpectrogramTxt()
    void testReadSpectrogramTxt_data();

    /// Tests parsing spectrogram series of a TXT file
    void testReadSpectrogramTxt();

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
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                              dateTime(2013, 9, 23, 9, 2, 30), dateTime(2013, 9, 23, 9, 3, 30),
                              dateTime(2013, 9, 23, 9, 4, 30), dateTime(2013, 9, 23, 9, 5, 30),
                              dateTime(2013, 9, 23, 9, 6, 30), dateTime(2013, 9, 23, 9, 7, 30),
                              dateTime(2013, 9, 23, 9, 8, 30), dateTime(2013, 9, 23, 9, 9, 30)})
               .setValuesData({-2.83950, -2.71850, -2.52150, -2.57633, -2.58050, -2.48325, -2.63025,
                               -2.55800, -2.43250, -2.42200});

    QTest::newRow("Valid file (value of first line is invalid but it is converted to NaN")
        << QStringLiteral("WrongValue.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                              dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({std::numeric_limits<double>::quiet_NaN(), -2.71850, -2.52150});

    QTest::newRow("Valid file that contains NaN values")
        << QStringLiteral("NaNValue.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{("nT"), true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                              dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({std::numeric_limits<double>::quiet_NaN(), -2.71850, -2.52150});

    // Valid files but with some invalid lines (wrong unit, wrong values, etc.)
    QTest::newRow("No unit file")
        << QStringLiteral("NoUnit.txt")
        << ExpectedResults<ScalarSeries>{}.setParsingOK(true).setXAxisUnit(Unit{"", true});

    QTest::newRow("Wrong unit file")
        << QStringLiteral("WrongUnit.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 0, 30), dateTime(2013, 9, 23, 9, 1, 30),
                              dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({-2.83950, -2.71850, -2.52150});

    QTest::newRow("Wrong results file (date of first line is invalid")
        << QStringLiteral("WrongDate.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({-2.71850, -2.52150});

    QTest::newRow("Wrong results file (too many values for first line")
        << QStringLiteral("TooManyValues.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({-2.71850, -2.52150});

    QTest::newRow("Wrong results file (x of first line is NaN")
        << QStringLiteral("NaNX.txt")
        << ExpectedResults<ScalarSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 9, 23, 9, 1, 30), dateTime(2013, 9, 23, 9, 2, 30)})
               .setValuesData({-2.71850, -2.52150});

    QTest::newRow("Invalid file type (vector)")
        << QStringLiteral("ValidVector1.txt")
        << ExpectedResults<ScalarSeries>{}.setParsingOK(true).setXAxisUnit(Unit{"nT", true});

    // Invalid files
    QTest::newRow("Invalid file (unexisting file)")
        << QStringLiteral("UnexistingFile.txt")
        << ExpectedResults<ScalarSeries>{}.setParsingOK(false);

    QTest::newRow("Invalid file (file not found on server)")
        << QStringLiteral("FileNotFound.txt")
        << ExpectedResults<ScalarSeries>{}.setParsingOK(false);
}

void TestAmdaResultParser::testReadScalarTxt()
{
    testRead<ScalarSeries>(AmdaResultParser::ValueType::SCALAR);
}

void TestAmdaResultParser::testReadSpectrogramTxt_data()
{
    testReadDataStructure<SpectrogramSeries>();

    // ////////// //
    // Test cases //
    // ////////// //

    // Valid files
    QTest::newRow("Valid file (three bands)")
        << QStringLiteral("spectro/ValidSpectrogram1.txt")
        << ExpectedResults<SpectrogramSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"t", true})
               .setXAxisData({dateTime(2012, 11, 6, 9, 14, 35), dateTime(2012, 11, 6, 9, 16, 10),
                              dateTime(2012, 11, 6, 9, 17, 45), dateTime(2012, 11, 6, 9, 19, 20),
                              dateTime(2012, 11, 6, 9, 20, 55)})
               .setYAxisEnabled(true)
               .setYAxisUnit(Unit{"eV"})
               .setYAxisData({5.75, 7.6, 10.05}) // middle of the intervals of each band
               .setValuesUnit(Unit{"eV/(cm^2-s-sr-eV)"})
               .setValuesData(QVector<QVector<double> >{
                   {16313.780, 12631.465, 8223.368, 27595.301, 12820.613},
                   {15405.838, 11957.925, 15026.249, 25617.533, 11179.109},
                   {8946.475, 18133.158, 10875.621, 24051.619, 19283.221}});

    auto fourBandsResult
        = ExpectedResults<SpectrogramSeries>{}
              .setParsingOK(true)
              .setXAxisUnit(Unit{"t", true})
              .setXAxisData({dateTime(2012, 11, 6, 9, 14, 35), dateTime(2012, 11, 6, 9, 16, 10),
                             dateTime(2012, 11, 6, 9, 17, 45), dateTime(2012, 11, 6, 9, 19, 20),
                             dateTime(2012, 11, 6, 9, 20, 55)})
              .setYAxisEnabled(true)
              .setYAxisUnit(Unit{"eV"})
              .setYAxisData({5.75, 7.6, 10.05, 13.}) // middle of the intervals of each band
              .setValuesUnit(Unit{"eV/(cm^2-s-sr-eV)"})
              .setValuesData(QVector<QVector<double> >{
                  {16313.780, 12631.465, 8223.368, 27595.301, 12820.613},
                  {15405.838, 11957.925, 15026.249, 25617.533, 11179.109},
                  {8946.475, 18133.158, 10875.621, 24051.619, 19283.221},
                  {20907.664, 32076.725, 13008.381, 13142.759, 23226.998}});

    QTest::newRow("Valid file (four bands)")
        << QStringLiteral("spectro/ValidSpectrogram2.txt") << fourBandsResult;
    QTest::newRow("Valid file (four unsorted bands)")
        << QStringLiteral("spectro/ValidSpectrogram3.txt")
        << fourBandsResult; // Bands and values are sorted

    auto nan = std::numeric_limits<double>::quiet_NaN();

    auto nanValuesResult
        = ExpectedResults<SpectrogramSeries>{}
              .setParsingOK(true)
              .setXAxisUnit(Unit{"t", true})
              .setXAxisData({dateTime(2012, 11, 6, 9, 14, 35), dateTime(2012, 11, 6, 9, 16, 10),
                             dateTime(2012, 11, 6, 9, 17, 45), dateTime(2012, 11, 6, 9, 19, 20),
                             dateTime(2012, 11, 6, 9, 20, 55)})
              .setYAxisEnabled(true)
              .setYAxisUnit(Unit{"eV"})
              .setYAxisData({5.75, 7.6, 10.05, 13.}) // middle of the intervals of each band
              .setValuesUnit(Unit{"eV/(cm^2-s-sr-eV)"})
              .setValuesData(
                  QVector<QVector<double> >{{nan, 12631.465, 8223.368, 27595.301, 12820.613},
                                            {15405.838, nan, nan, 25617.533, 11179.109},
                                            {8946.475, 18133.158, 10875.621, 24051.619, 19283.221},
                                            {nan, nan, nan, nan, nan}});

    QTest::newRow("Valid file (containing NaN values)")
        << QStringLiteral("spectro/ValidSpectrogramNaNValues.txt") << nanValuesResult;
    QTest::newRow("Valid file (containing fill values)")
        << QStringLiteral("spectro/ValidSpectrogramFillValues.txt")
        << nanValuesResult; // Fill values are replaced by NaN values in the data series

    QTest::newRow("Valid file (containing data holes, resolution = 3 minutes)")
        << QStringLiteral("spectro/ValidSpectrogramDataHoles.txt")
        << ExpectedResults<SpectrogramSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"t", true})
               .setXAxisData({dateTime(2011, 12, 10, 12, 10, 54), //
                              dateTime(2011, 12, 10, 12, 13, 54), // Data hole
                              dateTime(2011, 12, 10, 12, 16, 54), // Data hole
                              dateTime(2011, 12, 10, 12, 17, 23), //
                              dateTime(2011, 12, 10, 12, 20, 23), // Data hole
                              dateTime(2011, 12, 10, 12, 23, 23), // Data hole
                              dateTime(2011, 12, 10, 12, 23, 51), //
                              dateTime(2011, 12, 10, 12, 26, 51), // Data hole
                              dateTime(2011, 12, 10, 12, 29, 51), // Data hole
                              dateTime(2011, 12, 10, 12, 30, 19), //
                              dateTime(2011, 12, 10, 12, 33, 19), // Data hole
                              dateTime(2011, 12, 10, 12, 35, 04), //
                              dateTime(2011, 12, 10, 12, 36, 41), //
                              dateTime(2011, 12, 10, 12, 38, 18), //
                              dateTime(2011, 12, 10, 12, 39, 55)})
               .setYAxisEnabled(true)
               .setYAxisUnit(Unit{"eV"})
               .setYAxisData({16485.85, 20996.1}) // middle of the intervals of each band
               .setValuesUnit(Unit{"eV/(cm^2-s-sr-eV)"})
               .setValuesData(QVector<QVector<double> >{{2577578.000, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         2314121.500, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         2063608.750, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         2234525.500, //
                                                         nan,         // Data hole
                                                         1670215.250, //
                                                         1689243.250, //
                                                         1654617.125, //
                                                         1504983.750},
                                                        {2336016.000, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         1712093.125, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         1614491.625, //
                                                         nan,         // Data hole
                                                         nan,         // Data hole
                                                         1764516.500, //
                                                         nan,         // Data hole
                                                         1688078.500, //
                                                         1743183.500, //
                                                         1733603.250, //
                                                         1708356.500}});

    QTest::newRow(
        "Valid file (containing data holes at the beginning and the end, resolution = 4 minutes)")
        << QStringLiteral("spectro/ValidSpectrogramDataHoles2.txt")
        << ExpectedResults<SpectrogramSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"t", true})
               .setXAxisData({
                   dateTime(2011, 12, 10, 12, 2, 54),  // Data hole
                   dateTime(2011, 12, 10, 12, 6, 54),  // Data hole
                   dateTime(2011, 12, 10, 12, 10, 54), //
                   dateTime(2011, 12, 10, 12, 14, 54), // Data hole
                   dateTime(2011, 12, 10, 12, 17, 23), //
                   dateTime(2011, 12, 10, 12, 21, 23), // Data hole
                   dateTime(2011, 12, 10, 12, 23, 51), //
                   dateTime(2011, 12, 10, 12, 27, 51), // Data hole
                   dateTime(2011, 12, 10, 12, 30, 19), //
                   dateTime(2011, 12, 10, 12, 34, 19), // Data hole
                   dateTime(2011, 12, 10, 12, 35, 04), //
                   dateTime(2011, 12, 10, 12, 36, 41), //
                   dateTime(2011, 12, 10, 12, 38, 18), //
                   dateTime(2011, 12, 10, 12, 39, 55),
                   dateTime(2011, 12, 10, 12, 43, 55), // Data hole
                   dateTime(2011, 12, 10, 12, 47, 55), // Data hole
                   dateTime(2011, 12, 10, 12, 51, 55), // Data hole
                   dateTime(2011, 12, 10, 12, 55, 55), // Data hole
                   dateTime(2011, 12, 10, 12, 59, 55)  // Data hole
               })
               .setYAxisEnabled(true)
               .setYAxisUnit(Unit{"eV"})
               .setYAxisData({16485.85, 20996.1}) // middle of the intervals of each band
               .setValuesUnit(Unit{"eV/(cm^2-s-sr-eV)"})
               .setValuesData(QVector<QVector<double> >{{
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            2577578.000, //
                                                            nan,         // Data hole
                                                            2314121.500, //
                                                            nan,         // Data hole
                                                            2063608.750, //
                                                            nan,         // Data hole
                                                            2234525.500, //
                                                            nan,         // Data hole
                                                            1670215.250, //
                                                            1689243.250, //
                                                            1654617.125, //
                                                            1504983.750, //
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan          // Data hole
                                                        },
                                                        {
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            2336016.000, //
                                                            nan,         // Data hole
                                                            1712093.125, //
                                                            nan,         // Data hole
                                                            1614491.625, //
                                                            nan,         // Data hole
                                                            1764516.500, //
                                                            nan,         // Data hole
                                                            1688078.500, //
                                                            1743183.500, //
                                                            1733603.250, //
                                                            1708356.500, //
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan,         // Data hole
                                                            nan          // Data hole
                                                        }});

    // Invalid files
    QTest::newRow("Invalid file (inconsistent bands)")
        << QStringLiteral("spectro/InvalidSpectrogramWrongBands.txt")
        << ExpectedResults<SpectrogramSeries>{}.setParsingOK(false);
}

void TestAmdaResultParser::testReadSpectrogramTxt()
{
    testRead<SpectrogramSeries>(AmdaResultParser::ValueType::SPECTROGRAM);
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
        << ExpectedResults<VectorSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({dateTime(2013, 7, 2, 9, 13, 50), dateTime(2013, 7, 2, 9, 14, 6),
                              dateTime(2013, 7, 2, 9, 14, 22), dateTime(2013, 7, 2, 9, 14, 38),
                              dateTime(2013, 7, 2, 9, 14, 54), dateTime(2013, 7, 2, 9, 15, 10),
                              dateTime(2013, 7, 2, 9, 15, 26), dateTime(2013, 7, 2, 9, 15, 42),
                              dateTime(2013, 7, 2, 9, 15, 58), dateTime(2013, 7, 2, 9, 16, 14)})
               .setValuesData(
                   {{-0.332, -1.011, -1.457, -1.293, -1.217, -1.443, -1.278, -1.202, -1.22, -1.259},
                    {3.206, 2.999, 2.785, 2.736, 2.612, 2.564, 2.892, 2.862, 2.859, 2.764},
                    {0.058, 0.496, 1.018, 1.485, 1.662, 1.505, 1.168, 1.244, 1.15, 1.358}});

    // Valid files but with some invalid lines (wrong unit, wrong values, etc.)
    QTest::newRow("Invalid file type (scalar)")
        << QStringLiteral("ValidScalar1.txt")
        << ExpectedResults<VectorSeries>{}
               .setParsingOK(true)
               .setXAxisUnit(Unit{"nT", true})
               .setXAxisData({})
               .setValuesData(QVector<QVector<double> >{{}, {}, {}});
}

void TestAmdaResultParser::testReadVectorTxt()
{
    testRead<VectorSeries>(AmdaResultParser::ValueType::VECTOR);
}

QTEST_MAIN(TestAmdaResultParser)
#include "TestAmdaResultParser.moc"
