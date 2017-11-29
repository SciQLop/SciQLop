#ifndef SCIQLOP_DATASOURCEITEMBUILDER_H
#define SCIQLOP_DATASOURCEITEMBUILDER_H

#include <DataSource/DataSourceItem.h>

#include <memory>
#include <stack>

/**
 * @brief The DataSourceItemBuilder class aims to facilitate the creation of a DataSourceItem for unit tests
 * @sa DataSourceItem
 */
class DataSourceItemBuilder {
public:
    /// Inits root item
    DataSourceItemBuilder & root(const QString &name);
    DataSourceItemBuilder & root(QVariantHash data);

    /// Adds node into the current item
    DataSourceItemBuilder & node(const QString &name);
    DataSourceItemBuilder & node(QVariantHash data);

    /// Adds product into the current item
    DataSourceItemBuilder & product(const QString &name);
    DataSourceItemBuilder & product(QVariantHash data);

    /// Adds component into the current item
    DataSourceItemBuilder & component(const QString &name);
    DataSourceItemBuilder & component(QVariantHash data);

    /// Closes the build of the current item
    DataSourceItemBuilder& end();

    /// Creates the DataSourceItem
    std::shared_ptr<DataSourceItem> build();

private:
    DataSourceItemBuilder& append(DataSourceItemType type, const QString &name);
    DataSourceItemBuilder& append(DataSourceItemType type, QVariantHash data);

    std::shared_ptr<DataSourceItem> m_Root{nullptr};
    std::stack<DataSourceItem*> m_Items;
};

#endif // SCIQLOP_DATASOURCEITEMBUILDER_H
