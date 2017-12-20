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
    /// Key associated with the plugin of the item
    static const QString PLUGIN_DATA_KEY;
    /// Key associated with a unique id of the plugin
    static const QString ID_DATA_KEY;

    explicit DataSourceItem(DataSourceItemType type, const QString &name);
    explicit DataSourceItem(DataSourceItemType type, QVariantHash data = {});

    std::unique_ptr<DataSourceItem> clone() const;

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

    /**
     * Merge in the item the source item passed as parameter.
     *
     * The merge is done by adding as child of the item the complete tree represented by the source
     * item. If a part of the tree already exists in the item (based on the name of the nodes), it
     * is merged by completing the existing tree by items "leaves" (products, components or nodes
     * with no child).
     *
     * For example, with item representing the tree:
     * R (root node)
     *   - N1 (node)
     *     -- N11 (node)
     *        --- P1 (product)
     *        --- P2 (product)
     *   - N2 (node)
     *
     * and the source item representing the tree:
     * N1 (root node)
     *   - N11 (node)
     *     -- P3 (product)
     *   - N12 (node)
     *
     * The leaves of the source item to merge into the item are N1/N11/P3 and N1/N12 => we therefore
     * have the following merge result:
     * R
     *   - N1
     *     -- N11
     *        --- P1
     *        --- P2
     *        --- P3 (added leaf)
     *     -- N12 (added leaf)
     *
     * @param item the source item
     * @remarks No control is performed on products or components that are merged into the same tree
     * part (two products or components may have the same name)
     * @remarks the merge is made by copy (source item is not changed and still exists after the
     * operation)
     */
    void merge(const DataSourceItem &item);

    bool isRoot() const noexcept;

    QString name() const noexcept;

    /**
     * Get the item's parent
     * @return a pointer to the parent if it exists, nullptr if the item is a root
     */
    DataSourceItem *parentItem() const noexcept;

    /**
     * Gets the item's root
     * @return the top parent, the item itself if it's the root item
     */
    const DataSourceItem &rootItem() const noexcept;

    /**
     * Sets or appends a value to a key
     * @param key the key
     * @param value the value
     * @param append if true, the value is added to the values already existing for the key,
     * otherwise it replaces the existing values
     */
    void setData(const QString &key, const QVariant &value, bool append = false) noexcept;

    DataSourceItemType type() const noexcept;

    /**
     * @brief Searches the first child matching the specified data.
     * @param data The data to search.
     * @param recursive So the search recursively.
     * @return the item matching the data or nullptr if it was not found.
     */
    DataSourceItem *findItem(const QVariantHash &data, bool recursive);

    /**
     * @brief Searches the first child matching the specified \p ID_DATA_KEY in its metadata.
     * @param id The id to search.
     * @param recursive So the search recursively.
     * @return the item matching the data or nullptr if it was not found.
     */
    DataSourceItem *findItem(const QString &datasourceIdKey, bool recursive);

    bool operator==(const DataSourceItem &other);
    bool operator!=(const DataSourceItem &other);

private:
    class DataSourceItemPrivate;
    spimpl::unique_impl_ptr<DataSourceItemPrivate> impl;
};

#endif // SCIQLOP_DATASOURCEITEMMODEL_H
