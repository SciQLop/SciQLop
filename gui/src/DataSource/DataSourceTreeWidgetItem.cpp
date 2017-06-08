#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceTreeWidgetItem.h>

#include <SqpApplication.h>

Q_LOGGING_CATEGORY(LOG_DataSourceTreeWidgetItem, "DataSourceTreeWidgetItem")

namespace {

QIcon itemIcon(const DataSourceItem *dataSource)
{
    if (dataSource) {
        auto dataSourceType = dataSource->type();
        switch (dataSourceType) {
            case DataSourceItemType::NODE:
                return sqpApp->style()->standardIcon(QStyle::SP_DirIcon);
            case DataSourceItemType::PRODUCT:
                return sqpApp->style()->standardIcon(QStyle::SP_FileIcon);
            default:
                // No action
                break;
        }
    }

    // Default cases
    return QIcon{};
}

} // namespace

struct DataSourceTreeWidgetItem::DataSourceTreeWidgetItemPrivate {
    explicit DataSourceTreeWidgetItemPrivate(const DataSourceItem *data) : m_Data{data} {}

    /// Model used to retrieve data source information
    const DataSourceItem *m_Data;
};

DataSourceTreeWidgetItem::DataSourceTreeWidgetItem(const DataSourceItem *data, int type)
        : DataSourceTreeWidgetItem{nullptr, data, type}
{
}

DataSourceTreeWidgetItem::DataSourceTreeWidgetItem(QTreeWidget *parent, const DataSourceItem *data,
                                                   int type)
        : QTreeWidgetItem{parent, type},
          impl{spimpl::make_unique_impl<DataSourceTreeWidgetItemPrivate>(data)}
{
    // Sets the icon depending on the data source
    setIcon(0, itemIcon(impl->m_Data));
}

QVariant DataSourceTreeWidgetItem::data(int column, int role) const
{
    if (role == Qt::DisplayRole) {
        return (impl->m_Data) ? impl->m_Data->data(column) : QVariant{};
    }
    else {
        return QTreeWidgetItem::data(column, role);
    }
}

void DataSourceTreeWidgetItem::setData(int column, int role, const QVariant &value)
{
    // Data can't be changed by edition
    if (role != Qt::EditRole) {
        QTreeWidgetItem::setData(column, role, value);
    }
}
