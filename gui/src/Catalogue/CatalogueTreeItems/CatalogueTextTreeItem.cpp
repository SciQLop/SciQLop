#include "Catalogue/CatalogueTreeItems/CatalogueTextTreeItem.h"

#include <QIcon>

struct CatalogueTextTreeItem::CatalogueTextTreeItemPrivate {

    QString m_Text;
    QIcon m_Icon;
    bool m_IsEnabled = true;

    CatalogueTextTreeItemPrivate(const QIcon &icon, const QString &text)
            : m_Text(text), m_Icon(icon)
    {
    }
};


CatalogueTextTreeItem::CatalogueTextTreeItem(const QIcon &icon, const QString &text, int type)
        : CatalogueAbstractTreeItem(type),
          impl{spimpl::make_unique_impl<CatalogueTextTreeItemPrivate>(icon, text)}
{
}

QVariant CatalogueTextTreeItem::data(int column, int role) const
{
    if (column > 0) {
        return QVariant();
    }

    switch (role) {
        case Qt::DisplayRole:
            return impl->m_Text;
        case Qt::DecorationRole:
            return impl->m_Icon;
    }

    return QVariant();
}

Qt::ItemFlags CatalogueTextTreeItem::flags(int column) const
{
    Q_UNUSED(column);

    if (!impl->m_IsEnabled) {
        return Qt::NoItemFlags;
    }

    return Qt::ItemIsEnabled | Qt::ItemIsSelectable;
}

QString CatalogueTextTreeItem::text() const
{
    return impl->m_Text;
}

void CatalogueTextTreeItem::setEnabled(bool value)
{
    impl->m_IsEnabled = value;
}
