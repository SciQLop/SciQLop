#include "AmdaProvider.h"
#include "AmdaResultParser.h"

#include "SqpApplication.h"
#include <Data/DataSeries.h>
#include <Data/IDataSeries.h>
#include <Data/ScalarSeries.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController2.h>

#include <QObject>
#include <QtTest>

#include <memory>

// TEST with REF:
// AmdaData-2012-01-01-12-00-00_2012-01-03-12-00-00
// imf(0) - Type : Local Parameter @ CDPP/AMDA -
// Name : bx_gse - Units : nT - Size : 1 -
// Frame : GSE - Mission : ACE -
// Instrument : MFI - Dataset : mfi_final-prelim
// REFERENCE DOWNLOAD FILE =
// http://amdatest.irap.omp.eu/php/rest/getParameter.php?startTime=2012-01-01T12:00:00&stopTime=2012-01-03T12:00:00&parameterID=imf(0)&outputFormat=ASCII&timeFormat=ISO8601&gzip=0

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaAcquisition"}.absoluteFilePath();

/// Delay after each operation on the variable before validating it (in ms)
const auto OPERATION_DELAY = 10000;

template <typename T>
bool compareDataSeries(std::shared_ptr<IDataSeries> candidate, DateTimeRange candidateCacheRange,
                       std::shared_ptr<IDataSeries> reference)
{
    auto compareLambda = [](const auto &it1, const auto &it2) {
        return (it1.x() == it2.x()) && (it1.value() == it2.value());
    };

    auto candidateDS = std::dynamic_pointer_cast<T>(candidate);
    auto referenceDS = std::dynamic_pointer_cast<T>(reference);

    if (candidateDS && referenceDS) {

        auto itRefs
            = referenceDS->xAxisRange(candidateCacheRange.m_TStart, candidateCacheRange.m_TEnd);
        qDebug() << " DISTANCE" << std::distance(candidateDS->cbegin(), candidateDS->cend())
                 << std::distance(itRefs.first, itRefs.second);

        return std::equal(candidateDS->cbegin(), candidateDS->cend(), itRefs.first, itRefs.second,
                          compareLambda);
    }
    else {
        return false;
    }
}
}

class TestAmdaAcquisition : public QObject {
    Q_OBJECT

private slots:
    /// Input data for @sa testAcquisition()
    void testAcquisition_data();
    void testAcquisition();
};

void TestAmdaAcquisition::testAcquisition_data()
{
    // ////////////// //
    // Test structure //
    // ////////////// //

    QTest::addColumn<QString>("dataFilename");  // File containing expected data of acquisitions
    QTest::addColumn<DateTimeRange>("initialRange"); // First acquisition
    QTest::addColumn<std::vector<DateTimeRange> >("operations"); // Acquisitions to make

    // ////////// //
    // Test cases //
    // ////////// //

    auto dateTime = [](int year, int month, int day, int hours, int minutes, int seconds) {
        return DateUtils::secondsSinceEpoch(
            QDateTime{{year, month, day}, {hours, minutes, seconds}, Qt::UTC});
    };


    QTest::newRow("amda")
        << "AmdaData-2012-01-01-12-00-00_2012-01-03-12-00-00.txt"
        << DateTimeRange{dateTime(2012, 1, 2, 2, 3, 0), dateTime(2012, 1, 2, 2, 4, 0)}
        << std::vector<DateTimeRange>{
               // 2 : pan (jump) left for two min
               DateTimeRange{dateTime(2012, 1, 2, 2, 1, 0), dateTime(2012, 1, 2, 2, 2, 0)},
               // 3 : pan (jump) right for four min
               DateTimeRange{dateTime(2012, 1, 2, 2, 5, 0), dateTime(2012, 1, 2, 2, 6, 0)},
               // 4 : pan (overlay) right for 30 sec
               /*SqpRange{dateTime(2012, 1, 2, 2, 5, 30), dateTime(2012, 1, 2, 2, 6, 30)},
               // 5 : pan (overlay) left for 30 sec
               SqpRange{dateTime(2012, 1, 2, 2, 5, 0), dateTime(2012, 1, 2, 2, 6, 0)},
        // 6 : pan (overlay) left for 30 sec - BIS
        SqpRange{dateTime(2012, 1, 2, 2, 4, 30), dateTime(2012, 1, 2, 2, 5, 30)},
        // 7 : Zoom in Inside 20 sec range
        SqpRange{dateTime(2012, 1, 2, 2, 4, 50), dateTime(2012, 1, 2, 2, 5, 10)},
        // 8 : Zoom out Inside 20 sec range
        SqpRange{dateTime(2012, 1, 2, 2, 4, 30), dateTime(2012, 1, 2, 2, 5, 30)}*/};
}

void TestAmdaAcquisition::testAcquisition()
{
    /// @todo: update test to be compatible with AMDA v2

    // Retrieves data file
    QFETCH(QString, dataFilename);
    auto filePath = QFileInfo{TESTS_RESOURCES_PATH, dataFilename}.absoluteFilePath();
    auto results = AmdaResultParser::readTxt(filePath, DataSeriesType::SCALAR);

    /// Lambda used to validate a variable at each step
    auto validateVariable = [results](std::shared_ptr<Variable> variable, const DateTimeRange &range) {
        // Checks that the variable's range has changed
        qInfo() << tr("Compare var range vs range") << variable->range() << range;
        QCOMPARE(variable->range(), range);

        // Checks the variable's data series
        QVERIFY(compareDataSeries<ScalarSeries>(variable->dataSeries(), variable->cacheRange(),
                                                results));
        qInfo() << "\n";
    };

    // Creates variable
    QFETCH(DateTimeRange, initialRange);
    sqpApp->timeController().setDateTimeRange(initialRange);
    auto provider = std::make_shared<AmdaProvider>();
    auto variable = sqpApp->variableController().createVariable(
        "bx_gse", {{"dataType", "scalar"}, {"xml:id", "imf(0)"}}, provider, initialRange);

    QTest::qWait(OPERATION_DELAY);
    validateVariable(variable, initialRange);

    // Makes operations on the variable
    QFETCH(std::vector<DateTimeRange>, operations);
    for (const auto &operation : operations) {
        // Asks request on the variable and waits during its execution
        sqpApp->variableController().changeRange({variable}, operation);

        QTest::qWait(OPERATION_DELAY);
        validateVariable(variable, operation);
    }
}

int main(int argc, char *argv[])
{
    SqpApplication app(argc, argv);
    app.setAttribute(Qt::AA_Use96Dpi, true);
    TestAmdaAcquisition tc;
    QTEST_SET_MAIN_SOURCE_PATH
    return QTest::qExec(&tc, argc, argv);
}

// QTEST_MAIN(TestAmdaAcquisition)

#include "TestAmdaAcquisition.moc"
