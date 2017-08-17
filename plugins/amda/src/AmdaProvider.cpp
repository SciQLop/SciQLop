#include "AmdaProvider.h"
#include "AmdaDefs.h"
#include "AmdaResultParser.h"

#include <Common/DateUtils.h>
#include <Data/DataProviderParameters.h>
#include <Network/NetworkController.h>
#include <SqpApplication.h>
#include <Variable/Variable.h>

#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QTemporaryFile>
#include <QThread>

Q_LOGGING_CATEGORY(LOG_AmdaProvider, "AmdaProvider")

namespace {

/// URL format for a request on AMDA server. The parameters are as follows:
/// - %1: start date
/// - %2: end date
/// - %3: parameter id
const auto AMDA_URL_FORMAT = QStringLiteral(
    "http://amda.irap.omp.eu/php/rest/"
    "getParameter.php?startTime=%1&stopTime=%2&parameterID=%3&outputFormat=ASCII&"
    "timeFormat=ISO8601&gzip=0");

/// Dates format passed in the URL (e.g 2013-09-23T09:00)
const auto AMDA_TIME_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss");

/// Formats a time to a date that can be passed in URL
QString dateFormat(double sqpRange) noexcept
{
    auto dateTime = DateUtils::dateTime(sqpRange);
    return dateTime.toString(AMDA_TIME_FORMAT);
}

AmdaResultParser::ValueType valueType(const QString &valueType)
{
    if (valueType == QStringLiteral("scalar")) {
        return AmdaResultParser::ValueType::SCALAR;
    }
    else if (valueType == QStringLiteral("vector")) {
        return AmdaResultParser::ValueType::VECTOR;
    }
    else {
        return AmdaResultParser::ValueType::UNKNOWN;
    }
}

} // namespace

AmdaProvider::AmdaProvider()
{
    qCDebug(LOG_AmdaProvider()) << tr("AmdaProvider::AmdaProvider") << QThread::currentThread();
    if (auto app = sqpApp) {
        auto &networkController = app->networkController();
        connect(this, SIGNAL(requestConstructed(QNetworkRequest, QUuid,
                                                std::function<void(QNetworkReply *, QUuid)>)),
                &networkController,
                SLOT(onProcessRequested(QNetworkRequest, QUuid,
                                        std::function<void(QNetworkReply *, QUuid)>)));


        connect(&sqpApp->networkController(), SIGNAL(replyDownloadProgress(QUuid, double)), this,
                SIGNAL(dataProvidedProgress(QUuid, double)));
    }
}

void AmdaProvider::requestDataLoading(QUuid acqIdentifier, const DataProviderParameters &parameters)
{
    // NOTE: Try to use multithread if possible
    const auto times = parameters.m_Times;
    const auto data = parameters.m_Data;
    for (const auto &dateTime : qAsConst(times)) {
        this->retrieveData(acqIdentifier, dateTime, data);

        // TORM
        // QThread::msleep(200);
    }
}

void AmdaProvider::requestDataAborting(QUuid acqIdentifier)
{
    if (auto app = sqpApp) {
        auto &networkController = app->networkController();
        networkController.onReplyCanceled(acqIdentifier);
    }
}

void AmdaProvider::retrieveData(QUuid token, const SqpRange &dateTime, const QVariantHash &data)
{
    // Retrieves product ID from data: if the value is invalid, no request is made
    auto productId = data.value(AMDA_XML_ID_KEY).toString();
    if (productId.isNull()) {
        qCCritical(LOG_AmdaProvider()) << tr("Can't retrieve data: unknown product id");
        return;
    }
    qCDebug(LOG_AmdaProvider()) << tr("AmdaProvider::retrieveData") << dateTime;

    // Retrieves the data type that determines whether the expected format for the result file is
    // scalar, vector...
    auto productValueType = valueType(data.value(AMDA_DATA_TYPE_KEY).toString());

    // /////////// //
    // Creates URL //
    // /////////// //

    auto startDate = dateFormat(dateTime.m_TStart);
    auto endDate = dateFormat(dateTime.m_TEnd);

    auto url = QUrl{QString{AMDA_URL_FORMAT}.arg(startDate, endDate, productId)};
    qCInfo(LOG_AmdaProvider()) << tr("TORM AmdaProvider::retrieveData url:") << url;
    auto tempFile = std::make_shared<QTemporaryFile>();

    // LAMBDA
    auto httpDownloadFinished = [this, dateTime, tempFile,
                                 productValueType](QNetworkReply *reply, QUuid dataId) noexcept {

        // Don't do anything if the reply was abort
        if (reply->error() != QNetworkReply::OperationCanceledError) {

            if (tempFile) {
                auto replyReadAll = reply->readAll();
                if (!replyReadAll.isEmpty()) {
                    tempFile->write(replyReadAll);
                }
                tempFile->close();

                // Parse results file
                if (auto dataSeries
                    = AmdaResultParser::readTxt(tempFile->fileName(), productValueType)) {
                    emit dataProvided(dataId, dataSeries, dateTime);
                }
                else {
                    /// @todo ALX : debug
                }
            }
        }

    };
    auto httpFinishedLambda
        = [this, httpDownloadFinished, tempFile](QNetworkReply *reply, QUuid dataId) noexcept {

              // Don't do anything if the reply was abort
              if (reply->error() != QNetworkReply::OperationCanceledError) {
                  auto downloadFileUrl = QUrl{QString{reply->readAll()}};


                  qCInfo(LOG_AmdaProvider())
                      << tr("TORM AmdaProvider::retrieveData downloadFileUrl:") << downloadFileUrl;
                  // Executes request for downloading file //

                  // Creates destination file
                  if (tempFile->open()) {
                      // Executes request
                      emit requestConstructed(QNetworkRequest{downloadFileUrl}, dataId,
                                              httpDownloadFinished);
                  }
              }
          };

    // //////////////// //
    // Executes request //
    // //////////////// //
    emit requestConstructed(QNetworkRequest{url}, token, httpFinishedLambda);
}
