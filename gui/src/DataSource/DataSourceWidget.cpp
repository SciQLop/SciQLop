#include <DataSource/DataSourceWidget.h>

#include <ui_DataSourceWidget.h>

#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceTreeWidgetItem.h>

namespace {

/// Number of columns displayed in the tree
const auto TREE_NB_COLUMNS = 1;

/// Header labels for the tree
const auto TREE_HEADER_LABELS = QStringList{QObject::tr("Name")};

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
