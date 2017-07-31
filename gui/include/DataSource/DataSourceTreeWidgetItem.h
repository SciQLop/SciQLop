#ifndef SCIQLOP_DATASOURCETREEWIDGETITEM_H
#define SCIQLOP_DATASOURCETREEWIDGETITEM_H

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QTreeWidgetItem>

Q_DECLARE_LOGGING_CATEGORY(LOG_DataSourceTreeWidgetItem)

class DataSourceItem;

/**
 * @brief The DataSourceTreeWidgetItem is the graphical representation of a data source item. It is
 * intended to be displayed in a QTreeWidget.
 * @sa DataSourceItem
 */
class DataSourceTreeWidgetItem : public QTreeWidgetItem {
public:
    explicit DataSourceTreeWidgetItem(const DataSourceItem *data, int type = Type);
    explicit DataSourceTreeWidgetItem(QTreeWidget *parent, const DataSourceItem *data,
                                      int type = Type);

    const DataSourceItem *data() const;

    virtual QVariant data(int column, int role) const override;
    virtual void setData(int column, int role, const QVariant &value) override;

    /// @return the actions associated to the item
    QList<QAction *> actions() const noexcept;

private:
    class DataSourceTreeWidgetItemPrivate;
    spimpl::unique_impl_ptr<DataSourceTreeWidgetItemPrivate> impl;
};

#endif // SCIQLOP_DATASOURCETREEWIDGETITEM_H
