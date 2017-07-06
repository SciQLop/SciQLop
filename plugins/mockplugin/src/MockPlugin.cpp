#include "MockPlugin.h"
#include "CosinusProvider.h"

#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>

#include <SqpApplication.h>

Q_LOGGING_CATEGORY(LOG_MockPlugin, "MockPlugin")

namespace {

/// Name of the data source
const auto DATA_SOURCE_NAME = QStringLiteral("MMS");

/// Creates the data provider relative to the plugin
std::unique_ptr<IDataProvider> createDataProvider() noexcept
{
    return std::make_unique<CosinusProvider>();
}

std::unique_ptr<DataSourceItem> createProductItem(const QString &productName,
                                                  const QUuid &dataSourceUid)
{
    auto result = std::make_unique<DataSourceItem>(DataSourceItemType::PRODUCT, productName);

    // Add action to load product from DataSourceController
    result->addAction(std::make_unique<DataSourceItemAction>(
        QObject::tr("Load %1 product").arg(productName),
        [productName, dataSourceUid](DataSourceItem &item) {
            if (auto app = sqpApp) {
                app->dataSourceController().loadProductItem(dataSourceUid, item);
            }
        }));

    return result;
}

/// Creates the data source item relative to the plugin
std::unique_ptr<DataSourceItem> createDataSourceItem(const QUuid &dataSourceUid) noexcept
{
    // Magnetic field products
    auto magneticFieldFolder = std::make_unique<DataSourceItem>(DataSourceItemType::NODE,
                                                                QStringLiteral("Magnetic field"));
    magneticFieldFolder->appendChild(createProductItem(QStringLiteral("FGM"), dataSourceUid));
    magneticFieldFolder->appendChild(createProductItem(QStringLiteral("SC"), dataSourceUid));

    // Electric field products
    auto electricFieldFolder = std::make_unique<DataSourceItem>(DataSourceItemType::NODE,
                                                                QStringLiteral("Electric field"));

    // Root
    auto root = std::make_unique<DataSourceItem>(DataSourceItemType::NODE, DATA_SOURCE_NAME);
    root->appendChild(std::move(magneticFieldFolder));
    root->appendChild(std::move(electricFieldFolder));

    return root;
}

} // namespace

void MockPlugin::initialize()
{
    if (auto app = sqpApp) {
        // Registers to the data source controller
        auto &dataSourceController = app->dataSourceController();
        auto dataSourceUid = dataSourceController.registerDataSource(DATA_SOURCE_NAME);

        // Sets data source tree
        dataSourceController.setDataSourceItem(dataSourceUid, createDataSourceItem(dataSourceUid));

        // Sets data provider
        dataSourceController.setDataProvider(dataSourceUid, createDataProvider());
    }
    else {
        qCWarning(LOG_MockPlugin()) << tr("Can't access to SciQlop application");
    }
}
