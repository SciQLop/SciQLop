#pragma once
#include <Data/DataProviderParameters.h>
#include <Data/DataSeriesType.h>
#include <Data/IDataProvider.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>
#include <DataSource/datasources.h>

#include <QPair>
#include <QList>
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
    ~Product() = default;
};

template <typename T>
ScalarTimeSerie* make_scalar(T& t, T& y)
{
    return new ScalarTimeSerie { std::move(t.data), std::move(y.data) };
}

template <typename T>
VectorTimeSerie* make_vector(T& t, T& y)
{
    return new VectorTimeSerie { std::move(t.data), y.to_std_vect_vect() };
}

template <typename T>
MultiComponentTimeSerie* make_multi_comp(T& t, T& y)
{
    auto y_size = y.flat_size();
    auto t_size = t.flat_size();
    if (t_size && (y_size % t_size) == 0)
    {
        return new MultiComponentTimeSerie { std::move(t.data), std::move(y.data),
            { t_size, y_size / t_size } };
    }
    return nullptr;
}

template <typename T>
SpectrogramTimeSerie* make_spectro(T& t, T& y, T& z)
{
    auto z_size = z.flat_size();
    auto t_size = t.flat_size();
    if (t_size && (z_size % t_size) == 0)
    {
        return new SpectrogramTimeSerie { std::move(t.data), std::move(y.data), std::move(z.data),
            { t_size, z_size / t_size }, std::nan("1"), std::nan("1") };
    }
    return nullptr;
}


class PyDataProvider : public IDataProvider
{
public:
    PyDataProvider()
    {
        auto& dataSources = sqpApp->dataSources();
        dataSources.addProvider(this);
    }

    virtual ~PyDataProvider() {}

    virtual QPair<QPair<QPair<NpArray,NpArray>,NpArray>, DataSeriesType> get_data(
        const QMap<QString, QString>& key, double start_time, double stop_time)
    {
        (void)key, (void)start_time, (void)stop_time;
        return {};
    }

    virtual TimeSeries::ITimeSerie* getData(const DataProviderParameters& parameters) override
    {
        TimeSeries::ITimeSerie* ts = nullptr;
        if (parameters.m_Data.contains("name"))
        {
            QMap<QString, QString> metadata;
            std::for_each(parameters.m_Data.constKeyValueBegin(),
                parameters.m_Data.constKeyValueEnd(),
                [&metadata](const auto& item) { metadata[item.first] = item.second.toString(); });
            auto [data, type]
                = get_data(metadata, parameters.m_Range.m_TStart, parameters.m_Range.m_TEnd);

            auto& [axes, values] = data;
            auto& [x, y] = axes;
            switch (type)
            {
                case DataSeriesType::SCALAR:
                    ts = make_scalar(x, values);
                    break;
                case DataSeriesType::VECTOR:
                    ts = make_vector(x, values);
                    break;
                case DataSeriesType::MULTICOMPONENT:
                    ts = make_multi_comp(x, values);
                    break;
                case DataSeriesType::SPECTROGRAM:
                    ts = make_spectro(x, y, values);
                    break;
                default:
                    break;
            }
        }
        return ts;
    }

    inline void set_icon(const QString& path, const QString& name)
    {
        sqpApp->dataSources().setIcon(path, name);
    }

    inline void register_products(const QVector<Product*>& products)
    {
        auto& dataSources = sqpApp->dataSources();
        auto id = this->id();
        auto data_source_name = this->name();
        std::for_each(std::cbegin(products), std::cend(products),
            [&id, &dataSources](const Product* product) {
                dataSources.addDataSourceItem(id, product->path, product->metadata);
            });
    }
};
