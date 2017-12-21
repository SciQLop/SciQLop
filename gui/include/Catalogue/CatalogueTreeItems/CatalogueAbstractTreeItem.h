#ifndef SCIQLOP_CATALOGUEABSTRACTTREEITEM_H
#define SCIQLOP_CATALOGUEABSTRACTTREEITEM_H

#include <Common/spimpl.h>
#include <QVariant>
#include <QVector>

class QMimeData;

class CatalogueAbstractTreeItem {
public:
    constexpr static const int DEFAULT_TYPE = -1;

    CatalogueAbstractTreeItem(int type = DEFAULT_TYPE);
    virtual ~CatalogueAbstractTreeItem();

    void addChild(CatalogueAbstractTreeItem *child);
    void removeChild(CatalogueAbstractTreeItem *child);
    QVector<CatalogueAbstractTreeItem *> children() const;
    CatalogueAbstractTreeItem *parent() const;

    int type() const;
    QString text(int column = 0) const;

    virtual QVariant data(int column, int role) const;
    virtual Qt::ItemFlags flags(int column) const;
    virtual bool setData(int column, int role, const QVariant &value);
    virtual bool canDropMimeData(const QMimeData *data, Qt::DropAction action);
    virtual bool dropMimeData(const QMimeData *data, Qt::DropAction action);

private:
    class CatalogueAbstractTreeItemPrivate;
    spimpl::unique_impl_ptr<CatalogueAbstractTreeItemPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEABSTRACTTREEITEM_H
