#ifndef SCIQLOP_DATASOURCEITEM_H
#define SCIQLOP_DATASOURCEITEM_H

#include <Common/spimpl.h>

#include <QVariant>
#include <QVector>

class DataSourceItemAction;

/**
 * Possible types of an item
 */
enum class DataSourceItemType { NODE, PRODUCT };

/**
 * @brief The DataSourceItem class aims to represent a structure element of a data source.
 * A data source has a tree structure that is made up of a main DataSourceItem object (root)
 * containing other DataSourceItem objects (children).
 * For each DataSourceItem can be associated a set of data representing it.
 */
class DataSourceItem {
public:
    explicit DataSourceItem(DataSourceItemType type, QVector<QVariant> data = {});

    /// @return the actions of the item as a vector
    QVector<DataSourceItemAction *> actions() const noexcept;

    /**
     * Adds an action to the item. The item takes ownership of the action, and the action is
     * automatically associated to the item
     * @param action the action to add
     */
    void addAction(std::unique_ptr<DataSourceItemAction> action) noexcept;

    /**
     * Adds a child to the item. The item takes ownership of the child.
     * @param child the child to add
     */
    void appendChild(std::unique_ptr<DataSourceItem> child) noexcept;

    /**
     * Returns the item's child associated to an index
     * @param childIndex the index to search
     * @return a pointer to the child if index is valid, nullptr otherwise
     */
    DataSourceItem *child(int childIndex) const noexcept;

    int childCount() const noexcept;

    /**
     * Get the data associated to an index
     * @param dataIndex the index to search
     * @return the data found if index is valid, default QVariant otherwise
     */
    QVariant data(int dataIndex) const noexcept;

    QString name() const noexcept;

    /**
     * Get the item's parent
     * @return a pointer to the parent if it exists, nullptr if the item is a root
     */
    DataSourceItem *parentItem() const noexcept;

    DataSourceItemType type() const noexcept;

private:
    class DataSourceItemPrivate;
    spimpl::unique_impl_ptr<DataSourceItemPrivate> impl;
};

#endif // SCIQLOP_DATASOURCEITEMMODEL_H
