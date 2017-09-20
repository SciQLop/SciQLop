#include "CosinusProvider.h"

#include <Data/ScalarSeries.h>
#include <SqpApplication.h>

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
