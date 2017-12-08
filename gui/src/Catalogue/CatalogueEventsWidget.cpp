#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <Catalogue/CatalogueController.h>
#include <CatalogueDao.h>
#include <DBCatalogue.h>
#include <SqpApplication.h>


/// Format of the dates appearing in the label of a cursor
const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss");

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {
    void addEventItem(const QStringList &data, QTableWidget *tableWidget);

    enum class Column { Event, TStart, TEnd, Tags, Product, NbColumn };
    QStringList columnNames() { return QStringList{"Event", "TStart", "TEnd", "Tags", "Product"}; }

    QVector<DBEvent> m_Events;
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
        auto event = impl->m_Events.value(row);
        emit this->eventSelected(event);
    });

    connect(ui->tableWidget, &QTableWidget::currentItemChanged,
            [this](auto current, auto previous) {
                if (current && current->row() >= 0) {
                    auto event = impl->m_Events.value(current->row());
                    emit this->eventSelected(event);
                }
            });

    connect(ui->tableWidget, &QTableWidget::itemSelectionChanged, [this]() {
        auto selection = ui->tableWidget->selectedRanges();
        auto isNotMultiSelection
            = selection.isEmpty() || (selection.count() == 1 && selection.first().rowCount() == 1);
        ui->btnChart->setEnabled(isNotMultiSelection);
        ui->btnTime->setEnabled(isNotMultiSelection);
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

void CatalogueEventsWidget::populateWithCatalogue(const DBCatalogue &catalogue)
{
    ui->tableWidget->clearContents();
    ui->tableWidget->setRowCount(0);

    auto &dao = sqpApp->catalogueController().getDao();
    auto events = dao.getCatalogueEvents(catalogue);

    for (auto event : events) {
        impl->m_Events << event;

        auto tags = event.getTags();
        QString tagList;
        for (auto tag : tags) {
            tagList += tag.getName();
            tagList += ' ';
        }

        impl->addEventItem({event.getName(),
                            DateUtils::dateTime(event.getTStart()).toString(DATETIME_FORMAT),
                            DateUtils::dateTime(event.getTEnd()).toString(DATETIME_FORMAT), tagList,
                            event.getProduct()},
                           ui->tableWidget);
    }
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
