#ifndef SCIQLOP_CATALOGUETREEMODEL_H
#define SCIQLOP_CATALOGUETREEMODEL_H

#include <Common/spimpl.h>
#include <QAbstractItemModel>

class CatalogueAbstractTreeItem;

/**
 * @brief Model to display catalogue items based on QTreeWidgetItem
 * @warning Do not use the method QTreeWidgetItem::treeWidget for an item added to this model or the
 * application will crash
 */
class CatalogueTreeModel : public QAbstractItemModel {
    Q_OBJECT

signals:
    void itemRenamed(const QModelIndex &index);
    void itemDropped(const QModelIndex &parentIndex);

public:
    CatalogueTreeModel(QObject *parent = nullptr);

    enum class Column { Name, Validation, Count };

    QModelIndex addTopLevelItem(CatalogueAbstractTreeItem *item);
    QVector<CatalogueAbstractTreeItem *> topLevelItems() const;

    void addChildItem(CatalogueAbstractTreeItem *child, const QModelIndex &parentIndex);
    void removeChildItem(CatalogueAbstractTreeItem *child, const QModelIndex &parentIndex);
    /// Refresh the data for the specified index
    void refresh(const QModelIndex &index);

    CatalogueAbstractTreeItem *item(const QModelIndex &index) const;
    QModelIndex indexOf(CatalogueAbstractTreeItem *item, int column = 0) const;

    // model
    QModelIndex index(int row, int column,
                      const QModelIndex &parent = QModelIndex()) const override;
    QModelIndex parent(const QModelIndex &index) const override;
    int rowCount(const QModelIndex &parent) const override;
    int columnCount(const QModelIndex &parent) const override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    bool setData(const QModelIndex &index, const QVariant &value, int role) override;

    bool canDropMimeData(const QMimeData *data, Qt::DropAction action, int row, int column,
                         const QModelIndex &parent) const override;
    bool dropMimeData(const QMimeData *data, Qt::DropAction action, int row, int column,
                      const QModelIndex &parent) override;
    Qt::DropActions supportedDropActions() const;
    QStringList mimeTypes() const;

private:
    class CatalogueTreeModelPrivate;
    spimpl::unique_impl_ptr<CatalogueTreeModelPrivate> impl;
};

#endif // CATALOGUETREEMODEL_H
