#include "DataSource/DataSourceTreeWidget.h"
#include "Common/MimeTypesDef.h"
#include "DataSource/DataSourceController.h"
#include "DataSource/DataSourceItem.h"
#include "DataSource/DataSourceTreeWidgetItem.h"

#include "DragDropHelper.h"
#include "SqpApplication.h"

#include <QMimeData>

DataSourceTreeWidget::DataSourceTreeWidget(QWidget *parent) : QTreeWidget(parent) {}

QMimeData *DataSourceTreeWidget::mimeData(const QList<QTreeWidgetItem *> items) const
{
    auto mimeData = new QMimeData;

    // Basic check to ensure the item are correctly typed
    Q_ASSERT(items.isEmpty() || dynamic_cast<DataSourceTreeWidgetItem *>(items.first()) != nullptr);

    QVariantList productData;

    for (auto item : items) {
        auto dataSourceTreeItem = static_cast<DataSourceTreeWidgetItem *>(item);
        auto dataSource = dataSourceTreeItem->data();

        if (dataSource->type() == DataSourceItemType::COMPONENT
            || dataSource->type() == DataSourceItemType::PRODUCT) {
            auto metaData = dataSource->data();
            productData << metaData;
        }
    }

    auto encodedData = sqpApp->dataSourceController().mimeDataForProductsData(productData);
    mimeData->setData(MIME_TYPE_PRODUCT_LIST, encodedData);

    return mimeData;
}

void DataSourceTreeWidget::startDrag(Qt::DropActions supportedActions)
{
    // Resets the drag&drop operations before it's starting
    sqpApp->dragDropHelper().resetDragAndDrop();
    QTreeWidget::startDrag(supportedActions);
}
