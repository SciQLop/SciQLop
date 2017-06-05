#include <DataSource/DataSourceItem.h>

#include <QVector>

struct DataSourceItem::DataSourceItemPrivate {
    explicit DataSourceItemPrivate(QVector<QVariant> data)
            : m_Parent{nullptr}, m_Children{}, m_Data{std::move(data)}
    {
    }

    DataSourceItem *m_Parent;
    std::vector<std::unique_ptr<DataSourceItem> > m_Children;
    QVector<QVariant> m_Data;
};

DataSourceItem::DataSourceItem(QVector<QVariant> data)
        : impl{spimpl::make_unique_impl<DataSourceItemPrivate>(data)}
{
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

QVariant DataSourceItem::data(int dataIndex) const noexcept
{
    return impl->m_Data.value(dataIndex);
}

DataSourceItem *DataSourceItem::parentItem() const noexcept
{
    return impl->m_Parent;
}
