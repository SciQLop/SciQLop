#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>
#include <DataSource/DataSourceTreeWidgetItem.h>

#include <QAction>

Q_LOGGING_CATEGORY(LOG_DataSourceTreeWidgetItem, "DataSourceTreeWidgetItem")

namespace {

// Column indexes
const auto NAME_COLUMN = 0;

QIcon itemIcon(const DataSourceItem *dataSource)
{
    if (dataSource) {
        auto dataSourceType = dataSource->type();
        switch (dataSourceType) {
            case DataSourceItemType::NODE:
                return QIcon{":/icones/dataSourceNode.png"};
            case DataSourceItemType::PRODUCT:
                return QIcon{":/icones/dataSourceProduct.png"};
            case DataSourceItemType::COMPONENT:
                return QIcon{":/icones/dataSourceComponent.png"};
            default:
                // No action
                break;
        }

        qCWarning(LOG_DataSourceTreeWidgetItem())
            << QObject::tr("Can't set data source icon : unknown data source type");
    }
    else {
        qCWarning(LOG_DataSourceTreeWidgetItem())
            << QObject::tr("Can't set data source icon : the data source is null");
    }

    // Default cases
    return QIcon{};
}

} // namespace

struct DataSourceTreeWidgetItem::DataSourceTreeWidgetItemPrivate {
    explicit DataSourceTreeWidgetItemPrivate(const DataSourceItem *data) : m_Data{data} {}

    /// Model used to retrieve data source information
    const DataSourceItem *m_Data;
    /// Actions associated to the item. The parent of the item (QTreeWidget) takes the ownership of
    /// the actions
    QList<QAction *> m_Actions;
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

    // Generates tree actions based on the item actions
    auto createTreeAction = [this, &parent](const auto &itemAction) {
        auto treeAction = new QAction{itemAction->name(), parent};

        // Executes item action when tree action is triggered
        QObject::connect(treeAction, &QAction::triggered, itemAction,
                         &DataSourceItemAction::execute);

        return treeAction;
    };

    auto itemActions = impl->m_Data->actions();
    std::transform(std::cbegin(itemActions), std::cend(itemActions),
                   std::back_inserter(impl->m_Actions), createTreeAction);
}

QVariant DataSourceTreeWidgetItem::data(int column, int role) const
{
    if (role == Qt::DisplayRole) {
        if (impl->m_Data) {
            switch (column) {
                case NAME_COLUMN:
                    return impl->m_Data->name();
                default:
                    // No action
                    break;
            }

            qCWarning(LOG_DataSourceTreeWidgetItem())
                << QObject::tr("Can't get data (unknown column %1)").arg(column);
        }
        else {
            qCCritical(LOG_DataSourceTreeWidgetItem()) << QObject::tr("Can't get data (null item)");
        }

        return QVariant{};
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

QList<QAction *> DataSourceTreeWidgetItem::actions() const noexcept
{
    return impl->m_Actions;
}
