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
    if (item.type() == DataSourceItemType::PRODUCT) {
        auto itemName = item.name();

        item.addAction(std::make_unique<DataSourceItemAction>(
            QObject::tr("Load %1 product").arg(itemName),
            [itemName, dataSourceUid](DataSourceItem &item) {
                if (auto app = sqpApp) {
                    app->dataSourceController().loadProductItem(dataSourceUid, item);
                }
            }));
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
