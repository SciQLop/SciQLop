#pragma once
#include <Data/DataProviderParameters.h>
#include <Data/IDataProvider.h>
#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>
#include <QPair>
#include <SqpApplication.h>
// must be included last because of Python/Qt definition of slots
#include "numpy_wrappers.h"

struct Product
{
    QString path;
    std::vector<std::string> components;
    QMap<QString, QString> metadata;
    Product() = default;
    explicit Product(const QString& path, const std::vector<std::string>& components,
        const QMap<QString, QString>& metadata)
            : path { path }, components { components }, metadata { metadata }
    {
    }
    virtual ~Product() = default;
};

class PyDataProvider : public IDataProvider
{
public:
    PyDataProvider()
    {
        auto& dataSourceController = sqpApp->dataSourceController();
        dataSourceController.registerProvider(this);
    }

    virtual ~PyDataProvider() {}

    virtual QPair<NpArray, NpArray> getData(
        const std::string& key, double start_time, double stop_time)
    {
        (void)key, (void)start_time, (void)stop_time;
        return {};
    }

    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters) override
    {
        if (parameters.m_Data.contains("name"))
        {
            auto data = getData(parameters.m_Data["name"].toString().toStdString(),
                parameters.m_Range.m_TStart, parameters.m_Range.m_TEnd);
            // TODO add shape/type switch
            return new ScalarTimeSerie { data.first.to_std_vect(), data.second.to_std_vect() };
        }
        return nullptr;
    }


    inline void register_products(const QVector<Product*>& products)
    {
        auto& dataSourceController = sqpApp->dataSourceController();
        auto id = this->id();
        auto data_source_name = this->name();
        std::for_each(std::cbegin(products), std::cend(products),
            [&id, &dataSourceController](const Product* product) {
                dataSourceController.setDataSourceItem(id, product->path, product->metadata);
            });
    }
};


struct Providers
{
    Providers() = default;
    virtual ~Providers() = default;
    inline void register_provider(PyDataProvider* provider)
    {
        auto& dataSourceController = sqpApp->dataSourceController();
        dataSourceController.setDataProvider(
            provider->id(), std::unique_ptr<IDataProvider>(provider));
    }
};


inline ScalarTimeSerie test_PyDataProvider(PyDataProvider& prov)
{
    auto v = prov.getData("", 0., 0.);
    ScalarTimeSerie s;
    s.set_data(v.first.to_std_vect(), v.second.to_std_vect());
    return s;
}
