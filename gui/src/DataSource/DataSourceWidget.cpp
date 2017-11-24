#include <DataSource/DataSourceWidget.h>

#include <ui_DataSourceWidget.h>

#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceTreeWidgetHelper.h>
#include <DataSource/DataSourceTreeWidgetItem.h>

#include <QMenu>

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

DataSourceWidget::DataSourceWidget(QWidget *parent)
        : QWidget{parent},
          ui{new Ui::DataSourceWidget},
          m_Root{
              std::make_unique<DataSourceItem>(DataSourceItemType::NODE, QStringLiteral("Sources"))}
{
    ui->setupUi(this);

    // Set tree properties
    ui->treeWidget->setColumnCount(TREE_NB_COLUMNS);
    ui->treeWidget->setHeaderLabels(TREE_HEADER_LABELS);
    ui->treeWidget->setContextMenuPolicy(Qt::CustomContextMenu);

    // Connection to show a menu when right clicking on the tree
    connect(ui->treeWidget, &QTreeWidget::customContextMenuRequested, this,
            &DataSourceWidget::onTreeMenuRequested);

    // Connection to filter tree
    connect(ui->filterLineEdit, &QLineEdit::textChanged, this, &DataSourceWidget::filterChanged);

    // First init
    updateTreeWidget();
}

DataSourceWidget::~DataSourceWidget() noexcept
{
    delete ui;
}

void DataSourceWidget::addDataSource(DataSourceItem *dataSource) noexcept
{
    // Creates the item associated to the source and adds it to the tree widget. The tree widget
    // takes the ownership of the item
    if (dataSource) {
        ui->treeWidget->addTopLevelItem(createTreeWidgetItem(dataSource));
    }
}

void DataSourceWidget::updateTreeWidget() noexcept
{
    ui->treeWidget->clear();

    auto rootItem = createTreeWidgetItem(m_Root.get());
    ui->treeWidget->addTopLevelItem(rootItem);
    rootItem->setExpanded(true);

    // Sorts tree
    ui->treeWidget->setSortingEnabled(true);
    ui->treeWidget->sortByColumn(0, Qt::AscendingOrder);
}

void DataSourceWidget::filterChanged(const QString &text) noexcept
{
    auto validateItem = [&text](const DataSourceTreeWidgetItem &item) {
        auto regExp = QRegExp{text, Qt::CaseInsensitive, QRegExp::Wildcard};

        // An item is valid if any of its metadata validates the text filter
        auto itemMetadata = item.data()->data();
        auto itemMetadataEnd = itemMetadata.cend();
        auto acceptFilter
            = [&regExp](const auto &variant) { return variant.toString().contains(regExp); };

        return std::find_if(itemMetadata.cbegin(), itemMetadataEnd, acceptFilter)
               != itemMetadataEnd;
    };

    // Applies filter on tree widget
    DataSourceTreeWidgetHelper::filter(*ui->treeWidget, validateItem);
}

void DataSourceWidget::onTreeMenuRequested(const QPoint &pos) noexcept
{
    // Retrieves the selected item in the tree, and build the menu from its actions
    if (auto selectedItem = dynamic_cast<DataSourceTreeWidgetItem *>(ui->treeWidget->itemAt(pos))) {
        QMenu treeMenu{};
        treeMenu.addActions(selectedItem->actions());

        if (!treeMenu.isEmpty()) {
            treeMenu.exec(QCursor::pos());
        }
    }
}
