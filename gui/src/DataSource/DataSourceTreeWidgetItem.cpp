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
            case DataSourceItemType::NODE: {
                return dataSource->isRoot() ? QIcon{":/icones/dataSourceRoot.png"}
                                            : QIcon{":/icones/dataSourceNode.png"};
            }
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
        qCCritical(LOG_DataSourceTreeWidgetItem())
            << QObject::tr("Can't set data source icon : the data source is null");
    }

    // Default cases
    return QIcon{};
}

/// @return the tooltip text for a variant. The text depends on whether the data is a simple variant
/// or a list of variants
QString tooltipValue(const QVariant &variant) noexcept
{
    // If the variant is a list of variants, the text of the tooltip is of the form: {val1, val2,
    // ...}
    if (variant.canConvert<QVariantList>()) {
        auto valueString = QStringLiteral("{");

        auto variantList = variant.value<QVariantList>();
        for (auto it = variantList.cbegin(), end = variantList.cend(); it != end; ++it) {
            valueString.append(it->toString());

            if (std::distance(it, end) != 1) {
                valueString.append(", ");
            }
        }

        valueString.append(QStringLiteral("}"));

        return valueString;
    }
    else {
        return variant.toString();
    }
}

QString itemTooltip(const DataSourceItem *dataSource) noexcept
{
    // The tooltip displays all item's data
    if (dataSource) {
        auto result = QString{};

        const auto &data = dataSource->data();
        for (auto it = data.cbegin(), end = data.cend(); it != end; ++it) {
            result.append(QString{"<b>%1:</b> %2<br/>"}.arg(it.key(), tooltipValue(it.value())));
        }

        return result;
    }
    else {
        qCCritical(LOG_DataSourceTreeWidgetItem())
            << QObject::tr("Can't set data source tooltip : the data source is null");

        return QString{};
    }
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
    // Sets the icon and the tooltip depending on the data source
    setIcon(0, itemIcon(impl->m_Data));
    setToolTip(0, itemTooltip(impl->m_Data));

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

const DataSourceItem *DataSourceTreeWidgetItem::data() const
{
    return impl->m_Data;
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
