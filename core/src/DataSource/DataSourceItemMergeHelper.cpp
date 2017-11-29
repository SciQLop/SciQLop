#include "DataSource/DataSourceItemMergeHelper.h"

#include <DataSource/DataSourceItem.h>

namespace {

/**
 * Finds in a tree an item similar to the item passed in parameter
 * @param item the item for which to find a similar item
 * @param root the root item of the tree
 * @return the similar item if found, nullptr otherwise
 */
DataSourceItem *findSimilarItem(const DataSourceItem &item, const DataSourceItem &root)
{
    // An item is considered similar to the another item if:
    // - the items are both nodes AND
    // - the names of the items are identical

    if (item.type() != DataSourceItemType::NODE) {
        return nullptr;
    }

    DataSourceItem *result{nullptr};
    bool found{false};
    for (auto i = 0, count = root.childCount(); i < count && !found; ++i) {
        auto child = root.child(i);

        found = child->type() == DataSourceItemType::NODE
                && QString::compare(child->name(), item.name(), Qt::CaseInsensitive) == 0;
        if (found) {
            result = child;
        }
    }

    return result;
}

} // namespace

void DataSourceItemMergeHelper::merge(const DataSourceItem &source, DataSourceItem &dest)
{
    // Checks if the source item can be merged into the destination item (i.e. there is a child item
    // similar to the source item)
    if (auto subItem = findSimilarItem(source, dest)) {
        // If there is an item similar to the source item, applies the merge recursively
        for (auto i = 0, count = source.childCount(); i < count; ++i) {
            merge(*source.child(i), *subItem);
        }
    }
    else {
        // If no item is similar to the source item, the item is copied as the child of the
        // destination item
        dest.appendChild(source.clone());
    }
}
