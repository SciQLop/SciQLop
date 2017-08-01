#ifndef SCIQLOP_DATASOURCETREEWIDGETHELPER_H
#define SCIQLOP_DATASOURCETREEWIDGETHELPER_H

#include <functional>

class DataSourceTreeWidgetItem;
class QTreeWidget;

class DataSourceTreeWidgetHelper {
public:
    /// Signature of the function associated to the filtering action
    using FilterFunction = std::function<bool(const DataSourceTreeWidgetItem &dataSourceItem)>;

    /**
     * Filters a tree widget according to a function. If an item is valid according to this
     * function, all of its ancestors and children are shown
     * @param treeWidget the widget to filter
     * @param fun the filter function
     */
    static void filter(QTreeWidget &treeWidget, FilterFunction fun) noexcept;
};

#endif // SCIQLOP_DATASOURCETREEWIDGETHELPER_H
