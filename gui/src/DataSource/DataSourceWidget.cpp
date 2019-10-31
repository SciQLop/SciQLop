#include <DataSource/DataSourceWidget.h>

#include <ui_DataSourceWidget.h>

#include <DataSource/datasources.h>

#include <SqpApplication.h>


namespace
{

/// Number of columns displayed in the tree
const auto TREE_NB_COLUMNS = 1;

/// Header labels for the tree
const auto TREE_HEADER_LABELS = QStringList { QObject::tr("Name") };

} // namespace

DataSourceWidget::DataSourceWidget(QWidget* parent)
        : QWidget { parent }
        , ui { new Ui::DataSourceWidget }
{
    ui->setupUi(this);
    m_model_proxy.setSourceModel(&(sqpApp->dataSources()));
    ui->treeView->setModel(&m_model_proxy);
    ui->treeView->setDragEnabled(true);
    m_model_proxy.setFilterRole(Qt::ToolTipRole);
    m_model_proxy.setRecursiveFilteringEnabled(true);

    // Connection to filter tree
    connect(ui->filterLineEdit, &QLineEdit::textChanged, &m_model_proxy, static_cast<void (QSortFilterProxyModel::*)(const QString&)>(
        &QSortFilterProxyModel::setFilterRegExp));
    sqpApp->dataSources().addIcon("satellite",QVariant(QIcon(":/icones/satellite.svg")));
}

DataSourceWidget::~DataSourceWidget() noexcept
{
    delete ui;
}

