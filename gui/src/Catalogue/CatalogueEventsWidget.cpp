#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <QtDebug>

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

    connect(ui->tableWidget, &QTableWidget::cellClicked, [this](auto row, auto column) {
        auto event = ui->tableWidget->item(row, 0)->text();
        emit this->eventSelected(event);
    });

    connect(ui->tableWidget, &QTableWidget::currentItemChanged,
            [this](auto current, auto previous) {
                if (current && current->row() >= 0) {
                    auto event = ui->tableWidget->item(current->row(), 0)->text();
                    emit this->eventSelected(event);
                }
            });

    connect(ui->tableWidget, &QTableWidget::itemSelectionChanged, [this]() {
        auto selection = ui->tableWidget->selectedRanges();
        auto isSingleSelection = selection.count() == 1 && selection.first().rowCount() == 1;
        ui->btnChart->setEnabled(isSingleSelection);
        ui->btnTime->setEnabled(isSingleSelection);
    });

    Q_ASSERT(impl->columnNames().count() == (int)CatalogueEventsWidgetPrivate::Column::NbColumn);
    ui->tableWidget->setColumnCount((int)CatalogueEventsWidgetPrivate::Column::NbColumn);
    ui->tableWidget->setHorizontalHeaderLabels(impl->columnNames());
    ui->tableWidget->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->tableWidget->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    ui->tableWidget->horizontalHeader()->setSortIndicatorShown(true);
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}

void CatalogueEventsWidget::populateWithCatalogue(const QString &catalogue)
{
    ui->tableWidget->clearContents();
    ui->tableWidget->setRowCount(0);

    // TODO
    impl->addEventItem(
        {catalogue + " - Event 1", "12/12/2012 12:12", "12/12/2042 12:52", "cloud", "mfi/b_gse42"},
        ui->tableWidget);
    impl->addEventItem(
        {catalogue + " - Event 2", "12/12/2012 12:10", "12/12/2042 12:42", "Acloud", "mfi/b_gse1"},
        ui->tableWidget);
    impl->addEventItem(
        {catalogue + " - Event 3", "12/12/2012 12:22", "12/12/2042 12:12", "Gcloud", "mfi/b_gse2"},
        ui->tableWidget);
    impl->addEventItem(
        {catalogue + " - Event 4", "12/12/2012 12:00", "12/12/2042 12:62", "Bcloud", "mfi/b_gse3"},
        ui->tableWidget);
}

void CatalogueEventsWidget::CatalogueEventsWidgetPrivate::addEventItem(const QStringList &data,
                                                                       QTableWidget *tableWidget)
{
    tableWidget->setSortingEnabled(false);
    auto row = tableWidget->rowCount();
    tableWidget->setRowCount(row + 1);

    for (auto i = 0; i < (int)Column::NbColumn; ++i) {
        auto item = new QTableWidgetItem(data.value(i));
        item->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable);
        tableWidget->setItem(row, i, item);
    }
    tableWidget->setSortingEnabled(true);
}
