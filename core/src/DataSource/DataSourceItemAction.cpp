#include <DataSource/DataSourceItemAction.h>

#include <functional>

Q_LOGGING_CATEGORY(LOG_DataSourceItemAction, "DataSourceItemAction")

struct DataSourceItemAction::DataSourceItemActionPrivate {
    explicit DataSourceItemActionPrivate(const QString &name,
                                         DataSourceItemAction::ExecuteFunction fun)
            : m_Name{name}, m_Fun{std::move(fun)}, m_DataSourceItem{nullptr}
    {
    }

    QString m_Name;
    DataSourceItemAction::ExecuteFunction m_Fun;
    /// Item associated to the action (can be null, in which case the action will not be executed)
    DataSourceItem *m_DataSourceItem;
};

DataSourceItemAction::DataSourceItemAction(const QString &name, ExecuteFunction fun)
        : impl{spimpl::make_unique_impl<DataSourceItemActionPrivate>(name, std::move(fun))}
{
}

std::unique_ptr<DataSourceItemAction> DataSourceItemAction::clone() const
{
    return std::make_unique<DataSourceItemAction>(impl->m_Name, impl->m_Fun);
}

QString DataSourceItemAction::name() const noexcept
{
    return impl->m_Name;
}

void DataSourceItemAction::setDataSourceItem(DataSourceItem *dataSourceItem) noexcept
{
    impl->m_DataSourceItem = dataSourceItem;
}

void DataSourceItemAction::execute()
{
    if (impl->m_DataSourceItem) {
        impl->m_Fun(*impl->m_DataSourceItem);
    }
    else {
        qCDebug(LOG_DataSourceItemAction())
            << tr("Can't execute action : no item has been associated");
    }
}
