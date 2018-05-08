#include "MockPlugin.h"
#include "CosinusProvider.h"
#include "MockDefs.h"

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

std::unique_ptr<DataSourceItem> createProductItem(const QVariantHash &metaData,
                                                  const QUuid &dataSourceUid)
{
    auto result = std::make_unique<DataSourceItem>(DataSourceItemType::PRODUCT, metaData);

    // Adds plugin name to product metadata
    result->setData(DataSourceItem::PLUGIN_DATA_KEY, DATA_SOURCE_NAME);
    result->setData(DataSourceItem::ID_DATA_KEY, metaData.value(DataSourceItem::NAME_DATA_KEY));

    auto productName = metaData.value(DataSourceItem::NAME_DATA_KEY).toString();

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
                                                                QStringLiteral("_Magnetic field"));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Scalar 10 Hz")},
                           {COSINUS_TYPE_KEY, "scalar"},
                           {COSINUS_FREQUENCY_KEY, 10.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Scalar 60 Hz")},
                           {COSINUS_TYPE_KEY, "scalar"},
                           {COSINUS_FREQUENCY_KEY, 60.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Scalar 100 Hz")},
                           {COSINUS_TYPE_KEY, "scalar"},
                           {COSINUS_FREQUENCY_KEY, 100.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Vector 10 Hz")},
                           {COSINUS_TYPE_KEY, "vector"},
                           {COSINUS_FREQUENCY_KEY, 10.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Vector 60 Hz")},
                           {COSINUS_TYPE_KEY, "vector"},
                           {COSINUS_FREQUENCY_KEY, 60.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Vector 100 Hz")},
                           {COSINUS_TYPE_KEY, "vector"},
                           {COSINUS_FREQUENCY_KEY, 100.}},
                          dataSourceUid));
    magneticFieldFolder->appendChild(
        createProductItem({{DataSourceItem::NAME_DATA_KEY, QStringLiteral("Spectrogram 1 Hz")},
                           {COSINUS_TYPE_KEY, "spectrogram"},
                           {COSINUS_FREQUENCY_KEY, 1.}},
                          dataSourceUid));

    // Electric field products
    auto electricFieldFolder = std::make_unique<DataSourceItem>(DataSourceItemType::NODE,
                                                                QStringLiteral("_Electric field"));

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
