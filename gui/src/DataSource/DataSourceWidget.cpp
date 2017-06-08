#include <DataSource/DataSourceWidget.h>

#include <ui_DataSourceWidget.h>

#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceTreeWidgetItem.h>

namespace {

/// Number of columns displayed in the tree
const auto TREE_NB_COLUMNS = 1;

/// Header labels for the tree
const auto TREE_HEADER_LABELS = QStringList{QObject::tr("Name")};

/**
 * Creates the item associated to a data source
 * @param dataSource the data source for which to create the item
 * @return the new item
 */
DataSourceTreeWidgetItem *createTreeWidgetItem(DataSourceItem *dataSource)
{
    // Creates item for the data source
    auto item = new DataSourceTreeWidgetItem{dataSource};

    // Generates items for the children of the data source
    for (auto i = 0; i < dataSource->childCount(); ++i) {
        item->addChild(createTreeWidgetItem(dataSource->child(i)));
    }

    return item;
}

} // namespace

class DataSourceWidget::DataSourceWidgetPrivate {
public:
    explicit DataSourceWidgetPrivate(DataSourceWidget &widget)
            : m_Ui{std::make_unique<Ui::DataSourceWidget>()}
    {
        m_Ui->setupUi(&widget);

        // Set tree properties
        m_Ui->treeWidget->setColumnCount(TREE_NB_COLUMNS);
        m_Ui->treeWidget->setHeaderLabels(TREE_HEADER_LABELS);
    }

    std::unique_ptr<Ui::DataSourceWidget> m_Ui;
};

DataSourceWidget::DataSourceWidget(QWidget *parent)
        : QWidget{parent}, impl{spimpl::make_unique_impl<DataSourceWidgetPrivate>(*this)}
{
}

void DataSourceWidget::addDataSource(DataSourceItem *dataSource) noexcept
{
    // Creates the item associated to the source and adds it to the tree widget. The tree widget
    // takes the ownership of the item
    if (dataSource) {
        impl->m_Ui->treeWidget->addTopLevelItem(createTreeWidgetItem(dataSource));
    }
}
