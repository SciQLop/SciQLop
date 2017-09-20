#include "AmdaProvider.h"
#include "AmdaResultParser.h"

#include "SqpApplication.h"
#include <Data/DataSeries.h>
#include <Data/IDataSeries.h>
#include <Data/ScalarSeries.h>
#include <Time/TimeController.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

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
// http://amda.irap.omp.eu/php/rest/getParameter.php?startTime=2012-01-01T12:00:00&stopTime=2012-01-03T12:00:00&parameterID=imf(0)&outputFormat=ASCII&timeFormat=ISO8601&gzip=0

namespace {

/// Path for the tests
const auto TESTS_RESOURCES_PATH
    = QFileInfo{QString{AMDA_TESTS_RESOURCES_DIR}, "TestAmdaAcquisition"}.absoluteFilePath();

const auto TESTS_AMDA_REF_FILE = QString{"AmdaData-2012-01-01-12-00-00_2012-01-03-12-00-00.txt"};

template <typename T>
bool compareDataSeries(std::shared_ptr<IDataSeries> candidate, SqpRange candidateCacheRange,
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

        //        auto xcValue = candidateDS->valuesData()->data();
        //        auto dist = std::distance(itRefs.first, itRefs.second);
        //        auto it = itRefs.first;
        //        for (auto i = 0; i < dist - 1; ++i) {
        //            ++it;
        //            qInfo() << "END:" << it->value();
        //        }
        //        qDebug() << "END:" << it->value() << xcValue.last();

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
    void testAcquisition();
};

void TestAmdaAcquisition::testAcquisition()
{
    // READ the ref file:
    auto filePath = QFileInfo{TESTS_RESOURCES_PATH, TESTS_AMDA_REF_FILE}.absoluteFilePath();
    auto results = AmdaResultParser::readTxt(filePath, AmdaResultParser::ValueType::SCALAR);

    auto provider = std::make_shared<AmdaProvider>();
    auto timeController = std::make_unique<TimeController>();

    auto varRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 3, 0, 0}};
    auto varRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 4, 0, 0}};

    auto sqpR = SqpRange{DateUtils::secondsSinceEpoch(varRS), DateUtils::secondsSinceEpoch(varRE)};

    timeController->onTimeToUpdate(sqpR);

    QVariantHash metaData;
    metaData.insert("dataType", "scalar");
    metaData.insert("xml:id", "imf(0)");

    VariableController vc;
    vc.setTimeController(timeController.get());

    auto var = vc.createVariable("bx_gse", metaData, provider);

    // 1 : Variable creation

    qDebug() << " 1: TIMECONTROLLER" << timeController->dateTime();
    qDebug() << " 1: RANGE     " << var->range();
    qDebug() << " 1: CACHERANGE" << var->cacheRange();

    // wait for 10 sec before asking next request toi permit asynchrone process to finish.
    auto timeToWaitMs = 10000;

    QEventLoop loop;
    QTimer::singleShot(timeToWaitMs, &loop, &QEventLoop::quit);
    loop.exec();

    // Tests on acquisition operation

    int count = 1;

    auto requestDataLoading = [&vc, var, timeToWaitMs, results, &count](auto tStart, auto tEnd) {
        ++count;

        auto nextSqpR
            = SqpRange{DateUtils::secondsSinceEpoch(tStart), DateUtils::secondsSinceEpoch(tEnd)};
        vc.onRequestDataLoading(QVector<std::shared_ptr<Variable> >{} << var, nextSqpR,
                                var->range(), true);

        QEventLoop loop;
        QTimer::singleShot(timeToWaitMs, &loop, &QEventLoop::quit);
        loop.exec();

        qInfo() << count << "RANGE     " << var->range();
        qInfo() << count << "CACHERANGE" << var->cacheRange();

        QCOMPARE(var->range().m_TStart, nextSqpR.m_TStart);
        QCOMPARE(var->range().m_TEnd, nextSqpR.m_TEnd);

        // Verify dataserie
        QVERIFY(compareDataSeries<ScalarSeries>(var->dataSeries(), var->cacheRange(), results));

    };

    // 2 : pan (jump) left for one hour
    auto nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 1, 0, 0}};
    auto nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 2, 0, 0}};
    requestDataLoading(nextVarRS, nextVarRE);


    // 3 : pan (jump) right for one hour
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 5, 0, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 6, 0, 0}};
    requestDataLoading(nextVarRS, nextVarRE);

    // 4 : pan (overlay) right for 30 min
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 5, 30, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 6, 30, 0}};
    // requestDataLoading(nextVarRS, nextVarRE);

    // 5 : pan (overlay) left for 30 min
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 5, 0, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 6, 0, 0}};
    // requestDataLoading(nextVarRS, nextVarRE);

    // 6 : pan (overlay) left for 30 min - BIS
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 4, 30, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 5, 30, 0}};
    // requestDataLoading(nextVarRS, nextVarRE);

    // 7 : Zoom in Inside 20 min range
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 4, 50, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 5, 10, 0}};
    // requestDataLoading(nextVarRS, nextVarRE);

    // 8 : Zoom out Inside 2 hours range
    nextVarRS = QDateTime{QDate{2012, 01, 02}, QTime{2, 4, 0, 0}};
    nextVarRE = QDateTime{QDate{2012, 01, 02}, QTime{2, 6, 0, 0}};
    // requestDataLoading(nextVarRS, nextVarRE);


    // Close the app after 10 sec
    QTimer::singleShot(timeToWaitMs, &loop, &QEventLoop::quit);
    loop.exec();
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
