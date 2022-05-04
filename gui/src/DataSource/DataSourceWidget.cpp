#include <DataSource/DataSourceWidget.h>

#include <ui_DataSourceWidget.h>

#include <DataSource/datasources.h>

#include <QCompleter>
#include <SqpApplication.h>

#include <QAction>


namespace
{

/// Number of columns displayed in the tree
const auto TREE_NB_COLUMNS = 1;

/// Header labels for the tree
const auto TREE_HEADER_LABELS = QStringList { QObject::tr("Name") };

} // namespace

DataSourceWidget::DataSourceWidget(QWidget* parent)
        : QWidget { parent }, ui { new Ui::DataSourceWidget }
{
    ui->setupUi(this);
    m_model_proxy.setSourceModel(&(sqpApp->dataSources()));
    ui->treeView->setModel(&m_model_proxy);
    ui->treeView->setDragEnabled(true);
    m_model_proxy.setFilterRole(Qt::ToolTipRole);
    m_model_proxy.setRecursiveFilteringEnabled(true);

    // Connection to filter tree
    connect(ui->filterLineEdit, &QLineEdit::textChanged, &m_model_proxy,
        static_cast<void (QSortFilterProxyModel::*)(const QString&)>(
            &QSortFilterProxyModel::setFilterRegularExpression));
    sqpApp->dataSources().addIcon("satellite", QVariant(QIcon(":/icones/satellite.svg")));

    QAction* expandAll = new QAction("Expand all");
    QAction* collapseAll = new QAction("Collapse all");
    ui->treeView->addAction(expandAll);
    ui->treeView->addAction(collapseAll);
    ui->treeView->setContextMenuPolicy(Qt::ActionsContextMenu);
    connect(expandAll, &QAction::triggered, [treeView = ui->treeView](bool checked) {
        (void)checked;
        treeView->expandAll();
    });
    connect(collapseAll, &QAction::triggered, [treeView = ui->treeView](bool checked) {
        (void)checked;
        treeView->collapseAll();
    });

    QCompleter* completer = new QCompleter(this);
    completer->setModel(sqpApp->dataSources().completionModel());
    completer->setCaseSensitivity(Qt::CaseInsensitive);
    ui->filterLineEdit->setCompleter(completer);
}

DataSourceWidget::~DataSourceWidget() noexcept
{
    delete ui;
}
