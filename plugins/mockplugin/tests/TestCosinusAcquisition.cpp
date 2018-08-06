#include "CosinusProvider.h"
#include "MockDefs.h"

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

/**
 * Verifies that the data in the candidate series are identical to the data in the reference series
 * in a specific range
 * @param candidate the candidate data series
 * @param range the range to check
 * @param reference the reference data series
 * @return true if the data of the candidate series and the reference series are identical in the
 * range, false otherwise
 */
bool checkDataSeries(std::shared_ptr<IDataSeries> candidate, const DateTimeRange &range,
                     std::shared_ptr<IDataSeries> reference)
{
    if (candidate == nullptr || reference == nullptr) {
        return candidate == reference;
    }

    auto referenceIt = reference->xAxisRange(range.m_TStart, range.m_TEnd);

    qInfo() << "candidateSize" << std::distance(candidate->cbegin(), candidate->cend());
    qInfo() << "refSize" << std::distance(referenceIt.first, referenceIt.second);

    return std::equal(candidate->cbegin(), candidate->cend(), referenceIt.first, referenceIt.second,
                      [](const auto &it1, const auto &it2) {
                          // - milliseconds precision for time
                          // - 1e-6 precision for value
                          return std::abs(it1.x() - it2.x()) < 1e-3
                                 && std::abs(it1.value() - it2.value()) < 1e-6;
                      });
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

    QTest::addColumn<DateTimeRange>("referenceRange");           // Range for generating reference series
    QTest::addColumn<DateTimeRange>("initialRange");             // First acquisition
    QTest::addColumn<int>("operationDelay");                // Acquisitions to make
    QTest::addColumn<std::vector<DateTimeRange> >("operations"); // Acquisitions to make

    // ////////// //
    // Test cases //
    // ////////// //

    auto dateTime = [](int year, int month, int day, int hours, int minutes, int seconds) {
        return DateUtils::secondsSinceEpoch(
            QDateTime{{year, month, day}, {hours, minutes, seconds}, Qt::UTC});
    };

    QTest::newRow("cosinus")
        << DateTimeRange{dateTime(2017, 1, 1, 12, 0, 0), dateTime(2017, 1, 1, 13, 0, 0)}
        << DateTimeRange{dateTime(2017, 1, 1, 12, 30, 0), dateTime(2017, 1, 1, 12, 35, 1)} << 250
        << std::vector<DateTimeRange>{
               // Pan (jump) left
               DateTimeRange{dateTime(2017, 1, 1, 12, 45, 0), dateTime(2017, 1, 1, 12, 50, 0)},
               // Pan (jump) right
               DateTimeRange{dateTime(2017, 1, 1, 12, 15, 0), dateTime(2017, 1, 1, 12, 20, 0)},
               // Pan (overlay) right
               DateTimeRange{dateTime(2017, 1, 1, 12, 14, 0), dateTime(2017, 1, 1, 12, 19, 0)},
               // Pan (overlay) left
               DateTimeRange{dateTime(2017, 1, 1, 12, 15, 0), dateTime(2017, 1, 1, 12, 20, 0)},
               // Pan (overlay) left
               DateTimeRange{dateTime(2017, 1, 1, 12, 16, 0), dateTime(2017, 1, 1, 12, 21, 0)},
               // Zoom in
               DateTimeRange{dateTime(2017, 1, 1, 12, 17, 30), dateTime(2017, 1, 1, 12, 19, 30)},
               // Zoom out
               DateTimeRange{dateTime(2017, 1, 1, 12, 12, 30), dateTime(2017, 1, 1, 12, 24, 30)}};

    QTest::newRow("cosinus_big")
        << DateTimeRange{dateTime(2017, 1, 1, 1, 0, 0), dateTime(2017, 1, 5, 13, 0, 0)}
        << DateTimeRange{dateTime(2017, 1, 2, 6, 30, 0), dateTime(2017, 1, 2, 18, 30, 0)} << 5000
        << std::vector<DateTimeRange>{
               // Pan (jump) left
               DateTimeRange{dateTime(2017, 1, 1, 13, 30, 0), dateTime(2017, 1, 1, 18, 30, 0)},
               // Pan (jump) right
               DateTimeRange{dateTime(2017, 1, 3, 4, 30, 0), dateTime(2017, 1, 3, 10, 30, 0)},
               // Pan (overlay) right
               DateTimeRange{dateTime(2017, 1, 3, 8, 30, 0), dateTime(2017, 1, 3, 12, 30, 0)},
               // Pan (overlay) left
               DateTimeRange{dateTime(2017, 1, 2, 8, 30, 0), dateTime(2017, 1, 3, 10, 30, 0)},
               // Pan (overlay) left
               DateTimeRange{dateTime(2017, 1, 1, 12, 30, 0), dateTime(2017, 1, 3, 5, 30, 0)},
               // Zoom in
               DateTimeRange{dateTime(2017, 1, 2, 2, 30, 0), dateTime(2017, 1, 2, 8, 30, 0)},
               // Zoom out
               DateTimeRange{dateTime(2017, 1, 1, 14, 30, 0), dateTime(2017, 1, 3, 12, 30, 0)}};
}

void TestCosinusAcquisition::testAcquisition()
{
    // Retrieves reference range
    QFETCH(DateTimeRange, referenceRange);
    CosinusProvider referenceProvider{};
    auto dataSeries = referenceProvider.provideDataSeries(
        referenceRange, {{COSINUS_TYPE_KEY, "scalar"}, {COSINUS_FREQUENCY_KEY, 10.}});

    auto end = dataSeries->cend() - 1;
    qInfo() << dataSeries->nbPoints() << dataSeries->cbegin()->x() << end->x();

    /// Lambda used to validate a variable at each step
    auto validateVariable
        = [dataSeries](std::shared_ptr<Variable> variable, const DateTimeRange &range) {
              // Checks that the variable's range has changed
              qInfo() << "range vs expected range" << variable->range() << range;
              QCOMPARE(variable->range(), range);

              // Checks the variable's data series
              QVERIFY(checkDataSeries(variable->dataSeries(), variable->cacheRange(), dataSeries));
          };

    // Creates variable
    QFETCH(DateTimeRange, initialRange);
    sqpApp->timeController().setDateTimeRange(initialRange);
    auto provider = std::make_shared<CosinusProvider>();
    auto variable = sqpApp->variableController().createVariable(
        "MMS", {{COSINUS_TYPE_KEY, "scalar"}, {COSINUS_FREQUENCY_KEY, 10.}}, provider, initialRange);


    QFETCH(int, operationDelay);
    QTest::qWait(operationDelay);
    validateVariable(variable, initialRange);

    QTest::qWait(operationDelay);
    // Makes operations on the variable
    QFETCH(std::vector<DateTimeRange>, operations);
    for (const auto &operation : operations) {
        // Asks request on the variable and waits during its execution
        sqpApp->variableController().onRequestDataLoading({variable}, operation, false);

        QTest::qWait(operationDelay);
        validateVariable(variable, operation);
    }


    for (const auto &operation : operations) {
        // Asks request on the variable and waits during its execution
        sqpApp->variableController().onRequestDataLoading({variable}, operation, false);
    }
    QTest::qWait(operationDelay);
    validateVariable(variable, operations.back());
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
