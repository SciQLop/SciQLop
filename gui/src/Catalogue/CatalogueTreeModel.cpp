#include "Catalogue/CatalogueTreeModel.h"

#include <QTreeWidgetItem>
#include <memory>

struct CatalogueTreeModel::CatalogueTreeModelPrivate {
    std::unique_ptr<QTreeWidgetItem> m_RootItem = nullptr;

    CatalogueTreeModelPrivate() : m_RootItem{std::make_unique<QTreeWidgetItem>()} {}
};

CatalogueTreeModel::CatalogueTreeModel(QObject *parent)
        : QAbstractItemModel(parent), impl{spimpl::make_unique_impl<CatalogueTreeModelPrivate>()}
{
}

QModelIndex CatalogueTreeModel::addTopLevelItem(QTreeWidgetItem *item)
{
    beginInsertRows(QModelIndex(), impl->m_RootItem->childCount(), impl->m_RootItem->childCount());
    impl->m_RootItem->addChild(item);
    endInsertRows();

    return index(impl->m_RootItem->childCount() - 1, 0);
}

int CatalogueTreeModel::topLevelItemCount() const
{
    return impl->m_RootItem->childCount();
}

QTreeWidgetItem *CatalogueTreeModel::topLevelItem(int i) const
{
    return impl->m_RootItem->child(i);
}

void CatalogueTreeModel::addChildItem(QTreeWidgetItem *child, const QModelIndex &parentIndex)
{
    auto parentItem = item(parentIndex);
    beginInsertRows(parentIndex, parentItem->childCount(), parentItem->childCount());
    parentItem->addChild(child);
    endInsertRows();
}

QTreeWidgetItem *CatalogueTreeModel::item(const QModelIndex &index) const
{
    return static_cast<QTreeWidgetItem *>(index.internalPointer());
}

QModelIndex CatalogueTreeModel::indexOf(QTreeWidgetItem *item, int column) const
{
    auto parentItem = item->parent();
    if (!parentItem) {
        return QModelIndex();
    }

    auto row = parentItem->indexOfChild(item);
    return createIndex(row, column, item);
}

QModelIndex CatalogueTreeModel::index(int row, int column, const QModelIndex &parent) const
{
    if (!hasIndex(row, column, parent)) {
        return QModelIndex();
    }

    QTreeWidgetItem *parentItem = nullptr;

    if (!parent.isValid()) {
        parentItem = impl->m_RootItem.get();
    }
    else {
        parentItem = static_cast<QTreeWidgetItem *>(parent.internalPointer());
    }

    QTreeWidgetItem *childItem = parentItem->child(row);
    if (childItem) {
        return createIndex(row, column, childItem);
    }

    return QModelIndex();
}


QModelIndex CatalogueTreeModel::parent(const QModelIndex &index) const
{
    if (!index.isValid()) {
        return QModelIndex();
    }

    auto childItem = static_cast<QTreeWidgetItem *>(index.internalPointer());
    auto parentItem = childItem->parent();

    if (parentItem == nullptr || parentItem->parent() == nullptr) {
        return QModelIndex();
    }

    auto row = parentItem->parent()->indexOfChild(parentItem);
    return createIndex(row, 0, parentItem);
}

int CatalogueTreeModel::rowCount(const QModelIndex &parent) const
{
    QTreeWidgetItem *parentItem = nullptr;
    if (parent.column() > 0) {
        return 0;
    }

    if (!parent.isValid()) {
        parentItem = impl->m_RootItem.get();
    }
    else {
        parentItem = static_cast<QTreeWidgetItem *>(parent.internalPointer());
    }

    return parentItem->childCount();
}

int CatalogueTreeModel::columnCount(const QModelIndex &parent) const
{
    return (int)Column::Count;
}

Qt::ItemFlags CatalogueTreeModel::flags(const QModelIndex &index) const
{
    if (index.column() == (int)Column::Validation) {
        return Qt::NoItemFlags;
    }

    auto item = static_cast<QTreeWidgetItem *>(index.internalPointer());
    if (item) {
        return item->flags();
    }

    return Qt::NoItemFlags;
}

QVariant CatalogueTreeModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid()) {
        return QModelIndex();
    }

    auto item = static_cast<QTreeWidgetItem *>(index.internalPointer());
    if (item) {
        return item->data(index.column(), role);
    }

    return QModelIndex();
}

bool CatalogueTreeModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    if (!index.isValid()) {
        return false;
    }

    auto item = static_cast<QTreeWidgetItem *>(index.internalPointer());
    if (item) {
        item->setData(index.column(), role, value);

        if (index.column() == (int)Column::Name) {
            emit itemRenamed(index);
        }

        return true;
    }

    return false;
}
