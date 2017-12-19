#include "Catalogue/CatalogueTreeModel.h"
#include <Catalogue/CatalogueTreeItems/CatalogueAbstractTreeItem.h>

#include <QMimeData>
#include <memory>

#include <Common/MimeTypesDef.h>

struct CatalogueTreeModel::CatalogueTreeModelPrivate {
    std::unique_ptr<CatalogueAbstractTreeItem> m_RootItem = nullptr;

    CatalogueTreeModelPrivate() : m_RootItem{std::make_unique<CatalogueAbstractTreeItem>()} {}
};

CatalogueTreeModel::CatalogueTreeModel(QObject *parent)
        : QAbstractItemModel(parent), impl{spimpl::make_unique_impl<CatalogueTreeModelPrivate>()}
{
}

QModelIndex CatalogueTreeModel::addTopLevelItem(CatalogueAbstractTreeItem *item)
{
    auto nbTopLevelItems = impl->m_RootItem->children().count();
    beginInsertRows(QModelIndex(), nbTopLevelItems, nbTopLevelItems);
    impl->m_RootItem->addChild(item);
    endInsertRows();

    emit dataChanged(QModelIndex(), QModelIndex());

    return index(nbTopLevelItems, 0);
}

QVector<CatalogueAbstractTreeItem *> CatalogueTreeModel::topLevelItems() const
{
    return impl->m_RootItem->children();
}

void CatalogueTreeModel::addChildItem(CatalogueAbstractTreeItem *child,
                                      const QModelIndex &parentIndex)
{
    auto parentItem = item(parentIndex);
    int c = parentItem->children().count();
    beginInsertRows(parentIndex, c, c);
    parentItem->addChild(child);
    endInsertRows();

    emit dataChanged(QModelIndex(), QModelIndex());
}

CatalogueAbstractTreeItem *CatalogueTreeModel::item(const QModelIndex &index) const
{
    return static_cast<CatalogueAbstractTreeItem *>(index.internalPointer());
}

QModelIndex CatalogueTreeModel::indexOf(CatalogueAbstractTreeItem *item, int column) const
{
    auto parentItem = item->parent();
    if (!parentItem) {
        return QModelIndex();
    }

    auto row = parentItem->children().indexOf(item);
    return createIndex(row, column, item);
}

QModelIndex CatalogueTreeModel::index(int row, int column, const QModelIndex &parent) const
{
    if (column > 0) {
        int a = 0;
    }

    if (!hasIndex(row, column, parent)) {
        return QModelIndex();
    }

    CatalogueAbstractTreeItem *parentItem = nullptr;

    if (!parent.isValid()) {
        parentItem = impl->m_RootItem.get();
    }
    else {
        parentItem = item(parent);
    }

    auto childItem = parentItem->children().value(row);
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

    auto childItem = item(index);
    auto parentItem = childItem->parent();

    if (parentItem == nullptr || parentItem->parent() == nullptr) {
        return QModelIndex();
    }

    auto row = parentItem->parent()->children().indexOf(parentItem);
    return createIndex(row, 0, parentItem);
}

int CatalogueTreeModel::rowCount(const QModelIndex &parent) const
{
    CatalogueAbstractTreeItem *parentItem = nullptr;

    if (!parent.isValid()) {
        parentItem = impl->m_RootItem.get();
    }
    else {
        parentItem = item(parent);
    }

    return parentItem->children().count();
}

int CatalogueTreeModel::columnCount(const QModelIndex &parent) const
{
    return (int)Column::Count;
}

Qt::ItemFlags CatalogueTreeModel::flags(const QModelIndex &index) const
{
    auto treeItem = item(index);
    if (treeItem) {
        return treeItem->flags(index.column());
    }

    return Qt::NoItemFlags;
}

QVariant CatalogueTreeModel::data(const QModelIndex &index, int role) const
{
    auto treeItem = item(index);
    if (treeItem) {
        return treeItem->data(index.column(), role);
    }

    return QModelIndex();
}

bool CatalogueTreeModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    auto treeItem = item(index);
    if (treeItem) {
        auto result = treeItem->setData(index.column(), role, value);

        if (result && index.column() == (int)Column::Name) {
            emit itemRenamed(index);
        }

        return result;
    }

    return false;
}
bool CatalogueTreeModel::canDropMimeData(const QMimeData *data, Qt::DropAction action, int row,
                                         int column, const QModelIndex &parent) const
{
    auto draggedIndex = parent;
    auto draggedItem = item(draggedIndex);
    if (draggedItem) {
        return draggedItem->canDropMimeData(data, action);
    }

    return false;
}

bool CatalogueTreeModel::dropMimeData(const QMimeData *data, Qt::DropAction action, int row,
                                      int column, const QModelIndex &parent)
{
    return false;
}

Qt::DropActions CatalogueTreeModel::supportedDropActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

QStringList CatalogueTreeModel::mimeTypes() const
{
    return {MIME_TYPE_EVENT_LIST};
}
