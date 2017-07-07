#include "AmdaParser.h"

#include <DataSource/DataSourceItem.h>

#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

Q_LOGGING_CATEGORY(LOG_AmdaParser, "AmdaParser")

namespace {

// Significant keys of an AMDA's JSON file
const auto COMPONENT_KEY = QStringLiteral("component");
const auto PRODUCT_KEY = QStringLiteral("parameter");
const auto ROOT_KEY = QStringLiteral("dataCenter");

/// Returns the correct item type according to the key passed in parameter
DataSourceItemType itemType(const QString &key) noexcept
{
    if (key == PRODUCT_KEY) {
        return DataSourceItemType::PRODUCT;
    }
    else if (key == COMPONENT_KEY) {
        return DataSourceItemType::COMPONENT;
    }
    else {
        return DataSourceItemType::NODE;
    }
}

/**
 * Processes an entry of the JSON file to populate/create data source items
 * @param jsonKey the entry's key
 * @param jsonValue the entry's value
 * @param item the current item for which the entry processing will be applied
 * @param appendData flag indicating that the entry is part of an array. In the case of an array of
 * values, each value will be concatenated to the others (rather than replacing the others)
 */
void parseEntry(const QString &jsonKey, const QJsonValue &jsonValue, DataSourceItem &item,
                bool isArrayEntry = false)
{
    if (jsonValue.isObject()) {
        // Case of an object:
        // - a new data source item is created and
        // - parsing is called recursively to process the new item
        // - the new item is then added as a child of the former item
        auto object = jsonValue.toObject();

        auto newItem = std::make_unique<DataSourceItem>(itemType(jsonKey));

        for (auto it = object.constBegin(), end = object.constEnd(); it != end; ++it) {
            parseEntry(it.key(), it.value(), *newItem);
        }

        item.appendChild(std::move(newItem));
    }
    else if (jsonValue.isArray()) {
        // Case of an array: the item is populated with the arrays' content
        auto object = jsonValue.toArray();

        for (auto it = object.constBegin(), end = object.constEnd(); it != end; ++it) {
            parseEntry(jsonKey, *it, item, true);
        }
    }
    else {
        // Case of a simple value: we add a data to the item. If the simple value is a part of an
        // array, it is concatenated to the values already existing for this key
        item.setData(jsonKey, jsonValue.toVariant(), isArrayEntry);
    }
}

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

    // Makes the parsing
    auto rootObject = rootValue.toObject();
    auto rootItem = std::make_unique<DataSourceItem>(DataSourceItemType::NODE);

    for (auto it = rootObject.constBegin(), end = rootObject.constEnd(); it != end; ++it) {
        parseEntry(it.key(), it.value(), *rootItem);
    }

    return rootItem;
}
