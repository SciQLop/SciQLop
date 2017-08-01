#include "DataSource/DataSourceTreeWidgetHelper.h"
#include "DataSource/DataSourceTreeWidgetItem.h"

namespace {

bool filterTreeItem(DataSourceTreeWidgetItem &treeItem,
                    DataSourceTreeWidgetHelper::FilterFunction fun, bool parentValid = false)
{
    auto selfValid = parentValid || fun(treeItem);

    auto childValid = false;
    auto childCount = treeItem.childCount();
    for (auto i = 0; i < childCount; ++i) {
        if (auto childItem = dynamic_cast<DataSourceTreeWidgetItem *>(treeItem.child(i))) {
            childValid |= filterTreeItem(*childItem, fun, selfValid);
        }
    }

    auto valid = selfValid || childValid;

    treeItem.setHidden(!valid);

    return valid;
}

} // namespace

void DataSourceTreeWidgetHelper::filter(QTreeWidget &treeWidget, FilterFunction fun) noexcept
{
    auto itemCount = treeWidget.topLevelItemCount();
    for (auto i = 0; i < itemCount; ++i) {
        if (auto item = dynamic_cast<DataSourceTreeWidgetItem *>(treeWidget.topLevelItem(i))) {
            filterTreeItem(*item, fun);
        }
    }
}
