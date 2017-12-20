#ifndef SCIQLOP_CATALOGUETREEITEM_H
#define SCIQLOP_CATALOGUETREEITEM_H

#include <Catalogue/CatalogueTreeItems/CatalogueAbstractTreeItem.h>
#include <Common/spimpl.h>

class DBCatalogue;


class CatalogueTreeItem : public CatalogueAbstractTreeItem {
public:
    CatalogueTreeItem(std::shared_ptr<DBCatalogue> catalogue, const QIcon &icon, int type);

    QVariant data(int column, int role) const override;
    bool setData(int column, int role, const QVariant &value) override;
    Qt::ItemFlags flags(int column) const override;
    bool canDropMimeData(const QMimeData *data, Qt::DropAction action) override;
    bool dropMimeData(const QMimeData *data, Qt::DropAction action) override;

    /// Returns the catalogue represented by the item
    std::shared_ptr<DBCatalogue> catalogue() const;

private:
    class CatalogueTreeItemPrivate;
    spimpl::unique_impl_ptr<CatalogueTreeItemPrivate> impl;
};

#endif // SCIQLOP_CATALOGUETREEITEM_H
