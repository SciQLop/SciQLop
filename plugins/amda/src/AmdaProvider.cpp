#include "AmdaProvider.h"
#include <Data/DataProviderParameters.h>

#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QTemporaryFile>

Q_LOGGING_CATEGORY(LOG_AmdaProvider, "AmdaProvider")

namespace {

/// URL format for a request on AMDA server. The parameters are as follows:
/// - %1: start date
/// - %2: end date
/// - %3: parameter id
const auto AMDA_URL_FORMAT = QStringLiteral(
    "http://amda.irap.omp.eu/php/rest/"
    "getParameter.php?startTime=%1&stopTime=%2&parameterID=%3&sampling=60&outputFormat=ASCII&"
    "timeFormat=ISO8601&gzip=0");

/// Dates format passed in the URL (e.g 2013-09-23T09:00)
const auto AMDA_TIME_FORMAT = QStringLiteral("yyyy-MM-ddThh:ss");

/// Formats a time to a date that can be passed in URL
QString dateFormat(double sqpDateTime) noexcept
{
    auto dateTime = QDateTime::fromMSecsSinceEpoch(sqpDateTime * 1000.);
    return dateTime.toString(AMDA_TIME_FORMAT);
}

} // namespace

struct AmdaProvider::AmdaProviderPrivate {
    DataProviderParameters m_Params{};
    std::unique_ptr<QNetworkAccessManager> m_AccessManager{nullptr};
    QNetworkReply *m_Reply{nullptr};
    std::unique_ptr<QTemporaryFile> m_File{nullptr};
    QUuid m_Token;
};

AmdaProvider::AmdaProvider() : impl{spimpl::make_unique_impl<AmdaProviderPrivate>()}
{
}

void AmdaProvider::requestDataLoading(QUuid token, const QVector<SqpDateTime> &dateTimeList)
{
    // NOTE: Try to use multithread if possible
    for (const auto &dateTime : dateTimeList) {
        retrieveData(token, DataProviderParameters{dateTime});
    }
}

void AmdaProvider::retrieveData(QUuid token, const DataProviderParameters &parameters) const
{
    // /////////// //
    // Creates URL //
    // /////////// //

    auto startDate = dateFormat(parameters.m_Time.m_TStart);
    auto endDate = dateFormat(parameters.m_Time.m_TEnd);
    auto productId = QStringLiteral("imf(0)");

    auto url = QUrl{QString{AMDA_URL_FORMAT}.arg(startDate, endDate, productId)};

    // //////////////// //
    // Executes request //
    // //////////////// //

    impl->m_Token = token;
    impl->m_Params = parameters;
    impl->m_AccessManager = std::make_unique<QNetworkAccessManager>();
    impl->m_Reply = impl->m_AccessManager->get(QNetworkRequest{url});
    connect(impl->m_Reply, &QNetworkReply::finished, this, &AmdaProvider::httpFinished);
}

void AmdaProvider::httpFinished() noexcept
{
    // ////////////////////// //
    // Gets download file url //
    // ////////////////////// //

    auto downloadFileUrl = QUrl{QString{impl->m_Reply->readAll()}};

    // ///////////////////////////////////// //
    // Executes request for downloading file //
    // ///////////////////////////////////// //

    // Deletes old reply
    impl->m_Reply->deleteLater();
    impl->m_Reply = nullptr;

    // Creates destination file
    impl->m_File = std::make_unique<QTemporaryFile>();
    if (impl->m_File->open()) {
        qCDebug(LOG_AmdaProvider()) << "Temp file: " << impl->m_File->fileName();

        // Executes request
        impl->m_AccessManager = std::make_unique<QNetworkAccessManager>();
        impl->m_Reply = impl->m_AccessManager->get(QNetworkRequest{downloadFileUrl});
        connect(impl->m_Reply, &QNetworkReply::finished, this,
                &AmdaProvider::httpDownloadReadyRead);
        connect(impl->m_Reply, &QNetworkReply::finished, this, &AmdaProvider::httpDownloadFinished);
    }
}

void AmdaProvider::httpDownloadFinished() noexcept
{
    if (impl->m_File) {
        impl->m_File->close();
        impl->m_File = nullptr;
    }

    // Deletes reply
    impl->m_Reply->deleteLater();
    impl->m_Reply = nullptr;
}

void AmdaProvider::httpDownloadReadyRead() noexcept
{
    if (impl->m_File) {
        impl->m_File->write(impl->m_Reply->readAll());
    }
}
