#include "AmdaProvider.h"
#include "AmdaDefs.h"
#include "AmdaResultParser.h"
#include "AmdaServer.h"

#include <Common/DateUtils.h>
#include <Data/DataProviderParameters.h>
#include <Network/NetworkController.h>
#include <SqpApplication.h>
#include <Variable/Variable.h>

#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QTemporaryFile>
#include <QThread>
#include <QJsonDocument>
#include <Network/Downloader.h>

Q_LOGGING_CATEGORY(LOG_AmdaProvider, "AmdaProvider")

namespace {

/// URL format for a request on AMDA server. The parameters are as follows:
/// - %1: server URL
/// - %2: start date
/// - %3: end date
/// - %4: parameter id
/// AMDA V2: http://amdatest.irap.omp.eu/php/rest/
const auto AMDA_URL_FORMAT = QStringLiteral(
    "http://%1/php/rest/"
    "getParameter.php?startTime=%2&stopTime=%3&parameterID=%4&outputFormat=ASCII&"
    "timeFormat=ISO8601&gzip=0");

const auto AMDA_URL_FORMAT_WITH_TOKEN = QStringLiteral(
    "http://%1/php/rest/"
    "getParameter.php?startTime=%2&stopTime=%3&parameterID=%4&outputFormat=ASCII&"
    "timeFormat=ISO8601&gzip=0&"
    "token=%5");

const auto AMDA_TOKEN_URL_FORMAT = QStringLiteral(
    "http://%1/php/rest/"
    "auth.php");

/// Dates format passed in the URL (e.g 2013-09-23T09:00)
const auto AMDA_TIME_FORMAT = QStringLiteral("yyyy-MM-ddThh:mm:ss");

/// Formats a time to a date that can be passed in URL
QString dateFormat(double sqpRange) noexcept
{
    auto dateTime = DateUtils::dateTime(sqpRange);
    return dateTime.toString(AMDA_TIME_FORMAT);
}


} // namespace

AmdaProvider::AmdaProvider()
{

}

std::shared_ptr<IDataProvider> AmdaProvider::clone() const
{
    // No copy is made in the clone
    return std::make_shared<AmdaProvider>();
}

IDataSeries* AmdaProvider::getData(const DataProviderParameters &parameters)
{
    auto range = parameters.m_Times.front();
    auto metaData = parameters.m_Data;
    auto productId = metaData.value(AMDA_XML_ID_KEY).toString();
    auto productValueType
        = DataSeriesTypeUtils::fromString(metaData.value(AMDA_DATA_TYPE_KEY).toString());
    auto startDate = dateFormat(range.m_TStart);
    auto endDate = dateFormat(range.m_TEnd);
    QVariantHash urlProperties{{AMDA_SERVER_KEY, metaData.value(AMDA_SERVER_KEY)}};
    auto token_url = QString{AMDA_TOKEN_URL_FORMAT}.arg(AmdaServer::instance().url(urlProperties));
    auto response = Downloader::get(token_url);
    auto url = QString{AMDA_URL_FORMAT_WITH_TOKEN}.arg(AmdaServer::instance().url(urlProperties),
                                                 startDate, endDate, productId, QString(response.data()));
    response = Downloader::get(url);
    auto test = QJsonDocument::fromJson(response.data());
    url = test["dataFileURLs"].toString();
    response = Downloader::get(url);
    return AmdaResultParser::readTxt(QTextStream{response.data()},productValueType);
}

