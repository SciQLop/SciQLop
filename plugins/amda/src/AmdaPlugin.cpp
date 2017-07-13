#include "AmdaPlugin.h"
#include "AmdaParser.h"
#include "AmdaProvider.h"

#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>

#include <SqpApplication.h>

Q_LOGGING_CATEGORY(LOG_AmdaPlugin, "AmdaPlugin")

namespace {

/// Name of the data source
const auto DATA_SOURCE_NAME = QStringLiteral("AMDA");

/// Path of the file used to generate the data source item for AMDA
const auto JSON_FILE_PATH = QStringLiteral(":/samples/AmdaSample.json");

void associateActions(DataSourceItem &item, const QUuid &dataSourceUid)
{
    auto addLoadAction = [&item, dataSourceUid](const QString &label) {
        item.addAction(
            std::make_unique<DataSourceItemAction>(label, [dataSourceUid](DataSourceItem &item) {
                if (auto app = sqpApp) {
                    app->dataSourceController().loadProductItem(dataSourceUid, item);
                }
            }));
    };

    const auto itemType = item.type();
    if (itemType == DataSourceItemType::PRODUCT) {
        addLoadAction(QObject::tr("Load %1 product").arg(item.name()));
    }
    else if (itemType == DataSourceItemType::COMPONENT) {
        addLoadAction(QObject::tr("Load %1 component").arg(item.name()));
    }

    auto count = item.childCount();
    for (auto i = 0; i < count; ++i) {
        if (auto child = item.child(i)) {
            associateActions(*child, dataSourceUid);
        }
    }
}

} // namespace

void AmdaPlugin::initialize()
{
    if (auto app = sqpApp) {
        // Registers to the data source controller
        auto &dataSourceController = app->dataSourceController();
        auto dataSourceUid = dataSourceController.registerDataSource(DATA_SOURCE_NAME);

        // Sets data source tree
        if (auto dataSourceItem = AmdaParser::readJson(JSON_FILE_PATH)) {
            associateActions(*dataSourceItem, dataSourceUid);

            dataSourceController.setDataSourceItem(dataSourceUid, std::move(dataSourceItem));
        }
        else {
            qCCritical(LOG_AmdaPlugin()) << tr("No data source item could be generated for AMDA");
        }

        // Sets data provider
        dataSourceController.setDataProvider(dataSourceUid, std::make_unique<AmdaProvider>());
    }
    else {
        qCWarning(LOG_AmdaPlugin()) << tr("Can't access to SciQlop application");
    }
}
