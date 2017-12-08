#include "Catalogue/CatalogueTreeWidgetItem.h"

struct CatalogueTreeWidgetItem::CatalogueTreeWidgetItemPrivate {

    DBCatalogue m_Catalogue;

    CatalogueTreeWidgetItemPrivate(DBCatalogue catalogue) : m_Catalogue(catalogue) {}
};


CatalogueTreeWidgetItem::CatalogueTreeWidgetItem(DBCatalogue catalogue, int type)
        : QTreeWidgetItem(type),
          impl{spimpl::make_unique_impl<CatalogueTreeWidgetItemPrivate>(catalogue)}
{
}

QVariant CatalogueTreeWidgetItem::data(int column, int role) const
{
    switch (role) {
        case Qt::DisplayRole:
            return impl->m_Catalogue.getName();
        default:
            break;
    }

    return QTreeWidgetItem::data(column, role);
}

DBCatalogue CatalogueTreeWidgetItem::catalogue() const
{
    return impl->m_Catalogue;
}
