#ifndef SCIQLOP_CATALOGUETEXTTREEITEM_H
#define SCIQLOP_CATALOGUETEXTTREEITEM_H

#include <Catalogue/CatalogueTreeItems/CatalogueAbstractTreeItem.h>
#include <Common/spimpl.h>

class CatalogueTextTreeItem : public CatalogueAbstractTreeItem {
public:
    CatalogueTextTreeItem(const QIcon &icon, const QString &text, int type);

    QVariant data(int column, int role) const override;
    Qt::ItemFlags flags(int column) const override;

    QString text() const;

    void setEnabled(bool value);

private:
    class CatalogueTextTreeItemPrivate;
    spimpl::unique_impl_ptr<CatalogueTextTreeItemPrivate> impl;
};

#endif // SCIQLOP_CATALOGUETEXTTREEITEM_H
