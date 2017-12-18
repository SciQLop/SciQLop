#ifndef SCIQLOP_CATALOGUETREEMODEL_H
#define SCIQLOP_CATALOGUETREEMODEL_H

#include <Common/spimpl.h>
#include <QAbstractItemModel>
#include <QTreeWidgetItem>

/**
 * @brief Model to display catalogue items based on QTreeWidgetItem
 * @warning Do not use the method QTreeWidgetItem::treeWidget for an item added to this model or the application will crash
 */
class CatalogueTreeModel : public QAbstractItemModel {
    Q_OBJECT

signals:
    void itemRenamed(const QModelIndex &index);

public:
    CatalogueTreeModel(QObject *parent = nullptr);

    enum class Column { Name, Validation, Count };

    QModelIndex addTopLevelItem(QTreeWidgetItem *item);
    int topLevelItemCount() const;
    QTreeWidgetItem *topLevelItem(int i) const;

    void addChildItem(QTreeWidgetItem *child, const QModelIndex &parentIndex);

    QTreeWidgetItem *item(const QModelIndex &index) const;
    QModelIndex indexOf(QTreeWidgetItem *item, int column = 0) const;

    // model
    QModelIndex index(int row, int column,
                      const QModelIndex &parent = QModelIndex()) const override;
    QModelIndex parent(const QModelIndex &index) const override;
    int rowCount(const QModelIndex &parent) const override;
    int columnCount(const QModelIndex &parent) const override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    bool setData(const QModelIndex &index, const QVariant &value, int role) override;

private:
    class CatalogueTreeModelPrivate;
    spimpl::unique_impl_ptr<CatalogueTreeModelPrivate> impl;
};

#endif // CATALOGUETREEMODEL_H
