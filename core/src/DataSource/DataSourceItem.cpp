#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceItemAction.h>
#include <DataSource/DataSourceItemMergeHelper.h>

#include <QVector>

const QString DataSourceItem::NAME_DATA_KEY = QStringLiteral("name");
const QString DataSourceItem::PLUGIN_DATA_KEY = QStringLiteral("plugin");
const QString DataSourceItem::ID_DATA_KEY = QStringLiteral("uuid");

struct DataSourceItem::DataSourceItemPrivate {
    explicit DataSourceItemPrivate(DataSourceItemType type, QVariantHash data)
            : m_Parent{nullptr}, m_Children{}, m_Type{type}, m_Data{std::move(data)}, m_Actions{}
    {
    }

    DataSourceItem *m_Parent;
    std::vector<std::unique_ptr<DataSourceItem> > m_Children;
    DataSourceItemType m_Type;
    QVariantHash m_Data;
    std::vector<std::unique_ptr<DataSourceItemAction> > m_Actions;
};

DataSourceItem::DataSourceItem(DataSourceItemType type, const QString &name)
        : DataSourceItem{type, QVariantHash{{NAME_DATA_KEY, name}}}
{
}

DataSourceItem::DataSourceItem(DataSourceItemType type, QVariantHash data)
        : impl{spimpl::make_unique_impl<DataSourceItemPrivate>(type, std::move(data))}
{
}

std::unique_ptr<DataSourceItem> DataSourceItem::clone() const
{
    auto result = std::make_unique<DataSourceItem>(impl->m_Type, impl->m_Data);

    // Clones children
    for (const auto &child : impl->m_Children) {
        result->appendChild(std::move(child->clone()));
    }

    // Clones actions
    for (const auto &action : impl->m_Actions) {
        result->addAction(std::move(action->clone()));
    }

    return result;
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

QVariantHash DataSourceItem::data() const noexcept
{
    return impl->m_Data;
}

void DataSourceItem::merge(const DataSourceItem &item)
{
    DataSourceItemMergeHelper::merge(item, *this);
}

bool DataSourceItem::isRoot() const noexcept
{
    return impl->m_Parent == nullptr;
}

QString DataSourceItem::name() const noexcept
{
    return data(NAME_DATA_KEY).toString();
}

DataSourceItem *DataSourceItem::parentItem() const noexcept
{
    return impl->m_Parent;
}

const DataSourceItem &DataSourceItem::rootItem() const noexcept
{
    return isRoot() ? *this : parentItem()->rootItem();
}

void DataSourceItem::setData(const QString &key, const QVariant &value, bool append) noexcept
{
    auto it = impl->m_Data.constFind(key);
    if (append && it != impl->m_Data.constEnd()) {
        // Case of an existing value to which we want to add to the new value
        if (it->canConvert<QVariantList>()) {
            auto variantList = it->value<QVariantList>();
            variantList.append(value);

            impl->m_Data.insert(key, variantList);
        }
        else {
            impl->m_Data.insert(key, QVariantList{*it, value});
        }
    }
    else {
        // Other cases :
        // - new value in map OR
        // - replacement of an existing value (not appending)
        impl->m_Data.insert(key, value);
    }
}

DataSourceItemType DataSourceItem::type() const noexcept
{
    return impl->m_Type;
}

DataSourceItem *DataSourceItem::findItem(const QVariantHash &data, bool recursive)
{
    for (const auto &child : impl->m_Children) {
        if (child->impl->m_Data == data) {
            return child.get();
        }

        if (recursive) {
            if (auto foundItem = child->findItem(data, true)) {
                return foundItem;
            }
        }
    }

    return nullptr;
}

DataSourceItem *DataSourceItem::findItem(const QString &datasourceIdKey, bool recursive)
{
    for (const auto &child : impl->m_Children) {
        auto childId = child->impl->m_Data.value(ID_DATA_KEY);
        if (childId == datasourceIdKey) {
            return child.get();
        }

        if (recursive) {
            if (auto foundItem = child->findItem(datasourceIdKey, true)) {
                return foundItem;
            }
        }
    }

    return nullptr;
}

bool DataSourceItem::operator==(const DataSourceItem &other)
{
    // Compares items' attributes
    if (std::tie(impl->m_Type, impl->m_Data) == std::tie(other.impl->m_Type, other.impl->m_Data)) {
        // Compares contents of items' children
        return std::equal(std::cbegin(impl->m_Children), std::cend(impl->m_Children),
                          std::cbegin(other.impl->m_Children), std::cend(other.impl->m_Children),
                          [](const auto &itemChild, const auto &otherChild) {
                              return *itemChild == *otherChild;
                          });
    }
    else {
        return false;
    }
}

bool DataSourceItem::operator!=(const DataSourceItem &other)
{
    return !(*this == other);
}
