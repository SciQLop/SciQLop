#include "AmdaParser.h"

#include <DataSource/DataSourceItem.h>

#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>

Q_LOGGING_CATEGORY(LOG_AmdaParser, "AmdaParser")

namespace {

// Significant keys of an AMDA's JSON file
const auto ROOT_KEY = QStringLiteral("dataCenter");

} // namespace

std::unique_ptr<DataSourceItem> AmdaParser::readJson(const QString &filePath) noexcept
{
    QFile jsonFile{filePath};

    if (!jsonFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qCCritical(LOG_AmdaParser())
            << QObject::tr("Can't retrieve data source tree from file %1: %2")
                   .arg(filePath, jsonFile.errorString());
        return nullptr;
    }

    auto json = jsonFile.readAll();
    auto jsonDocument = QJsonDocument::fromJson(json);

    // Check preconditions for parsing
    if (!jsonDocument.isObject()) {
        qCCritical(LOG_AmdaParser())
            << QObject::tr(
                   "Can't retrieve data source tree from file %1: the file is malformed (there is "
                   "not one and only one root object)")
                   .arg(filePath);
        return nullptr;
    }

    auto jsonDocumentObject = jsonDocument.object();
    if (!jsonDocumentObject.contains(ROOT_KEY)) {
        qCCritical(LOG_AmdaParser())
            << QObject::tr(
                   "Can't retrieve data source tree from file %1: the file is malformed (the key "
                   "for the root element was not found (%2))")
                   .arg(filePath, ROOT_KEY);
        return nullptr;
    }

    auto rootValue = jsonDocumentObject.value(ROOT_KEY);
    if (!rootValue.isObject()) {
        qCCritical(LOG_AmdaParser())
            << QObject::tr(
                   "Can't retrieve data source tree from file %1: the file is malformed (the root "
                   "element is of the wrong type)")
                   .arg(filePath);
        return nullptr;
    }
    /// @todo ALX
    return nullptr;
}
