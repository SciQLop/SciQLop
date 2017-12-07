#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {
    void addEventItem(const QStringList &data, QTableWidget *tableWidget);

    enum class Column { Event, TStart, TEnd, Tags, Product, NbColumn };
    QStringList columnNames() { return QStringList{"Event", "TStart", "TEnd", "Tags", "Product"}; }
};


CatalogueEventsWidget::CatalogueEventsWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueEventsWidget),
          impl{spimpl::make_unique_impl<CatalogueEventsWidgetPrivate>()}
{
    ui->setupUi(this);

    connect(ui->btnTime, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnChart->setChecked(false);
        }
    });

    connect(ui->btnChart, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnTime->setChecked(false);
        }
    });

    Q_ASSERT(impl->columnNames().count() == (int)CatalogueEventsWidgetPrivate::Column::NbColumn);
    ui->tableWidget->setColumnCount((int)CatalogueEventsWidgetPrivate::Column::NbColumn);
    ui->tableWidget->setHorizontalHeaderLabels(impl->columnNames());
    ui->tableWidget->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->tableWidget->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    ui->tableWidget->horizontalHeader()->setSortIndicatorShown(true);


    // test
    impl->addEventItem({"Event 1", "12/12/2012 12:12", "12/12/2042 12:42", "cloud", "mfi/b_gse"},
                       ui->tableWidget);
    impl->addEventItem({"Event 2", "12/12/2012 12:12", "12/12/2042 12:42", "cloud", "mfi/b_gse"},
                       ui->tableWidget);
    impl->addEventItem({"Event 3", "12/12/2012 12:12", "12/12/2042 12:42", "cloud", "mfi/b_gse"},
                       ui->tableWidget);
    impl->addEventItem({"Event 4", "12/12/2012 12:12", "12/12/2042 12:42", "cloud", "mfi/b_gse"},
                       ui->tableWidget);
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}

void CatalogueEventsWidget::CatalogueEventsWidgetPrivate::addEventItem(const QStringList &data,
                                                                       QTableWidget *tableWidget)
{
    auto row = tableWidget->rowCount();
    tableWidget->setRowCount(row + 1);

    for (auto i = 0; i < (int)Column::NbColumn; ++i) {
        auto item = new QTableWidgetItem(data.value(i));
        item->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable);
        tableWidget->setItem(row, i, item);
    }
}
