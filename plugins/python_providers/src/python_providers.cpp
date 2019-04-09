#include "python_providers.h"
#include <Data/DataProviderParameters.h>
#include <Data/DateTimeRange.h>
#include <Data/IDataProvider.h>
#include <Data/ScalarTimeSerie.h>
#include <Data/SpectrogramTimeSerie.h>
#include <Data/TimeSeriesUtils.h>
#include <Data/VectorTimeSerie.h>
#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>
#include <QDir>
#include <QStandardPaths>
#include <QStringList>
#include <SqpApplication.h>
#include <TimeSeries.h>
#include <functional>
#include <iostream>


const auto DATA_SOURCE_NAME = QStringLiteral("PythonProviders");

class PythonProvider : public IDataProvider
{
public:
    explicit PythonProvider(PythonInterpreter::provider_funct_t f) : _pythonFunction { f } {}

    PythonProvider(const PythonProvider& other) : _pythonFunction { other._pythonFunction } {}

    std::shared_ptr<IDataProvider> clone() const override
    {
        return std::make_shared<PythonProvider>(*this);
    }
    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters) override
    {
        auto product = parameters.m_Data.value("PRODUCT", "").toString().toStdString();
        auto range = parameters.m_Range;
        std::vector<std::tuple<std::string, std::string>> metadata;
        std::transform(parameters.m_Data.constKeyValueBegin(), parameters.m_Data.constKeyValueEnd(),
            std::back_inserter(metadata), [](const auto& item) {
                return std::tuple<std::string, std::string> { item.first.toStdString(),
                    item.second.toString().toStdString() };
            });
        auto result = _pythonFunction(metadata, range.m_TStart, range.m_TEnd);
        return TimeSeriesUtils::copy(result);
    }

private:
    PythonInterpreter::provider_funct_t _pythonFunction;
};


void PythonProviders::initialize()
{
    _interpreter.add_register_callback(
        [this](const std::vector<PythonInterpreter::product_t>& product_list,
            PythonInterpreter::provider_funct_t f) { this->register_product(product_list, f); });

    for (const auto& path : QStandardPaths::standardLocations(QStandardPaths::AppLocalDataLocation))
    {
        auto dir = QDir(path + "/python");
        if (dir.exists())
        {
            for (const auto& entry :
                dir.entryInfoList(QDir::Files | QDir::NoDotAndDotDot, QDir::Name))
            {
                if (entry.isFile() && entry.suffix() == "py")
                {
                    _interpreter.eval(entry.absoluteFilePath().toStdString());
                }
            }
        }
    }
    _interpreter.release();
}

PythonProviders::~PythonProviders() {}

std::unique_ptr<DataSourceItem> make_folder_item(const QString& name)
{
    return std::make_unique<DataSourceItem>(DataSourceItemType::NODE, name);
}

template <typename T>
DataSourceItem* make_path_items(
    const T& path_list_begin, const T& path_list_end, DataSourceItem* root)
{
    std::for_each(path_list_begin, path_list_end, [&root](const auto& folder_name) mutable {
        auto folder_ptr = root->findItem(folder_name);
        if (folder_ptr == nullptr)
        {
            auto folder = make_folder_item(folder_name);
            folder_ptr = folder.get();
            root->appendChild(std::move(folder));
        }
        root = folder_ptr;
    });
    return root;
}

std::unique_ptr<DataSourceItem> make_product_item(
    const QVariantHash& metaData, const QUuid& dataSourceUid)
{
    auto result = std::make_unique<DataSourceItem>(DataSourceItemType::PRODUCT, metaData);

    // Adds plugin name to product metadata
    result->setData(DataSourceItem::PLUGIN_DATA_KEY, DATA_SOURCE_NAME);
    result->setData(DataSourceItem::ID_DATA_KEY, metaData.value(DataSourceItem::NAME_DATA_KEY));

    auto productName = metaData.value(DataSourceItem::NAME_DATA_KEY).toString();

    // Add action to load product from DataSourceController
    result->addAction(
        std::make_unique<DataSourceItemAction>(QObject::tr("Load %1 product").arg(productName),
            [productName, dataSourceUid](DataSourceItem& item) {
                if (auto app = sqpApp)
                {
                    app->dataSourceController().loadProductItem(dataSourceUid, item);
                }
            }));

    return result;
}

void PythonProviders::register_product(
    const std::vector<PythonInterpreter::product_t>& product_list,
    PythonInterpreter::provider_funct_t f)
{
    auto& dataSourceController = sqpApp->dataSourceController();
    QString test = DATA_SOURCE_NAME + QUuid::createUuid().toString();
    auto id = dataSourceController.registerDataSource(test);
    auto root = make_folder_item(test);
    std::for_each(std::cbegin(product_list), std::cend(product_list),
        [id, f, root = root.get()](const auto& product) {
            const auto& path = std::get<0>(product);
            auto path_list = QString::fromStdString(path).split('/');
            auto name = *(std::cend(path_list) - 1);
            auto path_item
                = make_path_items(std::cbegin(path_list), std::cend(path_list) - 1, root);
            QVariantHash metaData { { DataSourceItem::NAME_DATA_KEY, name } };
            std::for_each(std::cbegin(std::get<2>(product)), std::cend(std::get<2>(product)),
                [&metaData](const auto& mdata) {
                    metaData[QString::fromStdString(mdata.first)]
                        = QString::fromStdString(mdata.second);
                });
            path_item->appendChild(make_product_item(metaData, id));
        });
    dataSourceController.setDataSourceItem(id, std::move(root));
    dataSourceController.setDataProvider(id, std::make_unique<PythonProvider>(f));
}
