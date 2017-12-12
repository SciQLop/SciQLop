#include "Catalogue/CatalogueTreeWidgetItem.h"

struct CatalogueTreeWidgetItem::CatalogueTreeWidgetItemPrivate {

    DBCatalogue m_Catalogue;

    CatalogueTreeWidgetItemPrivate(DBCatalogue catalogue) : m_Catalogue(catalogue) {}
};


CatalogueTreeWidgetItem::CatalogueTreeWidgetItem(DBCatalogue catalogue, int type)
        : QTreeWidgetItem(type),
          impl{spimpl::make_unique_impl<CatalogueTreeWidgetItemPrivate>(catalogue)}
{
    setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsEditable);
}

QVariant CatalogueTreeWidgetItem::data(int column, int role) const
{
    switch (role) {
        case Qt::EditRole: // fallthrough
        case Qt::DisplayRole:
            return impl->m_Catalogue.getName();
        default:
            break;
    }

    return QTreeWidgetItem::data(column, role);
}

void CatalogueTreeWidgetItem::setData(int column, int role, const QVariant &value)
{
    if (role == Qt::EditRole && column == 0) {
        auto newName = value.toString();
        setText(0, newName);
        impl->m_Catalogue.setName(newName);
    }
    else {
        QTreeWidgetItem::setData(column, role, value);
    }
}

DBCatalogue CatalogueTreeWidgetItem::catalogue() const
{
    return impl->m_Catalogue;
}
