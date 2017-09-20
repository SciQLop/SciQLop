#include "CosinusProvider.h"

#include <Data/DataProviderParameters.h>
#include <Data/ScalarSeries.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <QObject>
#include <QtTest>

#include <cmath>
#include <memory>

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH = QFileInfo{
    QString{MOCKPLUGIN_TESTS_RESOURCES_DIR},
    "TestCosinusAcquisition"}.absoluteFilePath();

/// Format of dates in data files
const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss:zzz");

/// Delay after each operation on the variable before validating it (in ms)
const auto OPERATION_DELAY = 250;

/**
 * Verifies that the data in the candidate series are identical to the data in the reference series
 * in a specific range
 * @param candidate the candidate data series
 * @param range the range to check
 * @param reference the reference data series
 * @return true if the data of the candidate series and the reference series are identical in the
 * range, false otherwise
 */
bool checkDataSeries(std::shared_ptr<IDataSeries> candidate, const SqpRange &range,
                     std::shared_ptr<IDataSeries> reference)
{
    if (candidate == nullptr || reference == nullptr) {
        return candidate == reference;
    }

    auto referenceIt = reference->xAxisRange(range.m_TStart, range.m_TEnd);

    return std::equal(candidate->cbegin(), candidate->cend(), referenceIt.first, referenceIt.second,
                      [](const auto &it1, const auto &it2) {
                          // - milliseconds precision for time
                          // - 1e-6 precision for value
                          return std::abs(it1.x() - it2.x()) < 1e-3
                                 && std::abs(it1.value() - it2.value()) < 1e-6;
                      });
}

/// Generates the data series from the reading of a data stream
std::shared_ptr<IDataSeries> readDataStream(QTextStream &stream)
{
    std::vector<double> xAxisData, valuesData;

    QString line{};
    while (stream.readLineInto(&line)) {
        // Separates date (x-axis data) to value data
        auto splitLine = line.split('\t');
        if (splitLine.size() == 2) {
            // Converts datetime to double
            auto dateTime = QDateTime::fromString(splitLine[0], DATETIME_FORMAT);
            dateTime.setTimeSpec(Qt::UTC);
            xAxisData.push_back(DateUtils::secondsSinceEpoch(dateTime));

            valuesData.push_back(splitLine[1].toDouble());
        }
    }

    return std::make_shared<ScalarSeries>(std::move(xAxisData), std::move(valuesData),
                                          Unit{{}, true}, Unit{});
}

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
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QString>("dataFilename");  // File containing expected data of acquisitions
    QTest::addColumn<SqpRange>("initialRange"); // First acquisition
    QTest::addColumn<std::vector<SqpRange> >("operations"); // Acquisitions to make
}

void TestCosinusAcquisition::testAcquisition()
{
    // Retrieves data file
    QFETCH(QString, dataFilename);

    auto dataFilePath = QFileInfo{TESTS_RESOURCES_PATH, dataFilename}.absoluteFilePath();
    QFile dataFile{dataFilePath};

    if (dataFile.open(QFile::ReadOnly)) {
        // Generates data series to compare with
        QTextStream dataStream{&dataFile};
        auto dataSeries = readDataStream(dataStream);

        /// Lambda used to validate a variable at each step
        auto validateVariable = [dataSeries](std::shared_ptr<Variable> variable,
                                             const SqpRange &range) {
            // Checks that the variable's range has changed
            QCOMPARE(variable->range(), range);

            // Checks the variable's data series
            QVERIFY(checkDataSeries(variable->dataSeries(), variable->cacheRange(), dataSeries));
        };

        // Creates variable
        QFETCH(SqpRange, initialRange);
        sqpApp->timeController().onTimeToUpdate(initialRange);
        auto provider = std::make_shared<CosinusProvider>();
        auto variable = sqpApp->variableController().createVariable("MMS", {}, provider);

        QTest::qWait(OPERATION_DELAY);
        validateVariable(variable, initialRange);

        // Makes operations on the variable
        QFETCH(std::vector<SqpRange>, operations);
        for (const auto &operation : operations) {
            // Asks request on the variable and waits during its execution
            sqpApp->variableController().onRequestDataLoading({variable}, operation,
                                                              variable->range(), true);

            QTest::qWait(OPERATION_DELAY);
            validateVariable(variable, operation);
        }
    }
    else {
        QFAIL("Can't read input data file");
    }
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
