#ifndef SCIQLOP_DATASOURCEITEM_H
#define SCIQLOP_DATASOURCEITEM_H

#include "CoreGlobal.h"

#include <Common/spimpl.h>

#include <QVariant>
#include <QVector>

class DataSourceItemAction;

/**
 * Possible types of an item
 */
enum class DataSourceItemType { NODE, PRODUCT, COMPONENT };

/**
 * @brief The DataSourceItem class aims to represent a structure element of a data source.
 * A data source has a tree structure that is made up of a main DataSourceItem object (root)
 * containing other DataSourceItem objects (children).
 * For each DataSourceItem can be associated a set of data representing it.
 */
class SCIQLOP_CORE_EXPORT DataSourceItem {
public:
    /// Key associated with the name of the item
    static const QString NAME_DATA_KEY;

    explicit DataSourceItem(DataSourceItemType type, const QString &name);
    explicit DataSourceItem(DataSourceItemType type, QVariantHash data = {});

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
     * Get the data associated to a key
     * @param key the key to search
     * @return the data found if key is valid, default QVariant otherwise
     */
    QVariant data(const QString &key) const noexcept;

    /// Gets all data
    QVariantHash data() const noexcept;

    bool isRoot() const noexcept;

    QString name() const noexcept;

    /**
     * Get the item's parent
     * @return a pointer to the parent if it exists, nullptr if the item is a root
     */
    DataSourceItem *parentItem() const noexcept;

    /**
     * Sets or appends a value to a key
     * @param key the key
     * @param value the value
     * @param append if true, the value is added to the values already existing for the key,
     * otherwise it replaces the existing values
     */
    void setData(const QString &key, const QVariant &value, bool append = false) noexcept;

    DataSourceItemType type() const noexcept;

    bool operator==(const DataSourceItem &other);
    bool operator!=(const DataSourceItem &other);

private:
    class DataSourceItemPrivate;
    spimpl::unique_impl_ptr<DataSourceItemPrivate> impl;
};

#endif // SCIQLOP_DATASOURCEITEMMODEL_H
