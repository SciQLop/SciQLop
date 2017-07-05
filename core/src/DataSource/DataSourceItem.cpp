#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>

#include <QVector>

const QString DataSourceItem::NAME_DATA_KEY = QStringLiteral("name");

struct DataSourceItem::DataSourceItemPrivate {
    explicit DataSourceItemPrivate(DataSourceItemType type, QHash<QString, QVariant> data)
            : m_Parent{nullptr}, m_Children{}, m_Type{type}, m_Data{std::move(data)}, m_Actions{}
    {
    }

    DataSourceItem *m_Parent;
    std::vector<std::unique_ptr<DataSourceItem> > m_Children;
    DataSourceItemType m_Type;
    QHash<QString, QVariant> m_Data;
    std::vector<std::unique_ptr<DataSourceItemAction> > m_Actions;
};

DataSourceItem::DataSourceItem(DataSourceItemType type, const QString &name)
        : DataSourceItem{type, QHash<QString, QVariant>{{NAME_DATA_KEY, name}}}
{
}

DataSourceItem::DataSourceItem(DataSourceItemType type, QHash<QString, QVariant> data)
        : impl{spimpl::make_unique_impl<DataSourceItemPrivate>(type, std::move(data))}
{
}

QVector<DataSourceItemAction *> DataSourceItem::actions() const noexcept
{
    auto result = QVector<DataSourceItemAction *>{};

    std::transform(std::cbegin(impl->m_Actions), std::cend(impl->m_Actions),
                   std::back_inserter(result), [](const auto &action) { return action.get(); });

    return result;
}

void DataSourceItem::addAction(std::unique_ptr<DataSourceItemAction> action) noexcept
{
    action->setDataSourceItem(this);
    impl->m_Actions.push_back(std::move(action));
}

void DataSourceItem::appendChild(std::unique_ptr<DataSourceItem> child) noexcept
{
    child->impl->m_Parent = this;
    impl->m_Children.push_back(std::move(child));
}

DataSourceItem *DataSourceItem::child(int childIndex) const noexcept
{
    if (childIndex < 0 || childIndex >= childCount()) {
        return nullptr;
    }
    else {
        return impl->m_Children.at(childIndex).get();
    }
}

int DataSourceItem::childCount() const noexcept
{
    return impl->m_Children.size();
}

QVariant DataSourceItem::data(const QString &key) const noexcept
{
    return impl->m_Data.value(key);
}

QString DataSourceItem::name() const noexcept
{
    return data(NAME_DATA_KEY).toString();
}

DataSourceItem *DataSourceItem::parentItem() const noexcept
{
    return impl->m_Parent;
}

DataSourceItemType DataSourceItem::type() const noexcept
{
    return impl->m_Type;
}
