#include "Catalogue/CatalogueTreeItems/CatalogueAbstractTreeItem.h"

struct CatalogueAbstractTreeItem::CatalogueAbstractTreeItemPrivate {
    int m_Type;
    QVector<CatalogueAbstractTreeItem *> m_Children;
    CatalogueAbstractTreeItem *m_Parent = nullptr;

    CatalogueAbstractTreeItemPrivate(int type) : m_Type(type) {}
};

CatalogueAbstractTreeItem::CatalogueAbstractTreeItem(int type)
        : impl{spimpl::make_unique_impl<CatalogueAbstractTreeItemPrivate>(type)}
{
}

CatalogueAbstractTreeItem::~CatalogueAbstractTreeItem()
{
    qDeleteAll(impl->m_Children);
}

void CatalogueAbstractTreeItem::addChild(CatalogueAbstractTreeItem *child)
{
    impl->m_Children << child;
    child->impl->m_Parent = this;
}

QVector<CatalogueAbstractTreeItem *> CatalogueAbstractTreeItem::children() const
{
    return impl->m_Children;
}

CatalogueAbstractTreeItem *CatalogueAbstractTreeItem::parent() const
{
    return impl->m_Parent;
}

int CatalogueAbstractTreeItem::type() const
{
    return impl->m_Type;
}

QString CatalogueAbstractTreeItem::text(int column) const
{
    return data(0, Qt::DisplayRole).toString();
}

QVariant CatalogueAbstractTreeItem::data(int column, int role) const
{
    Q_UNUSED(column);
    Q_UNUSED(role);
    return QVariant();
}

Qt::ItemFlags CatalogueAbstractTreeItem::flags(int column) const
{
    Q_UNUSED(column);
    return Qt::NoItemFlags;
}

bool CatalogueAbstractTreeItem::setData(int column, int role, const QVariant &value)
{
    Q_UNUSED(column);
    Q_UNUSED(role);
    Q_UNUSED(value);

    return false;
}

bool CatalogueAbstractTreeItem::canDropMimeData(const QMimeData *data, Qt::DropAction action)
{
    Q_UNUSED(data);
    Q_UNUSED(action);
    return false;
}
