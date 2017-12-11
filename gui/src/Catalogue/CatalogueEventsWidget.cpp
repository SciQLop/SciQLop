#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueEventsTableModel.h>
#include <CatalogueDao.h>
#include <DBCatalogue.h>
#include <SqpApplication.h>


/// Format of the dates appearing in the label of a cursor
const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss");

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {

    CatalogueEventsTableModel *m_Model = nullptr;
};


CatalogueEventsWidget::CatalogueEventsWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueEventsWidget),
          impl{spimpl::make_unique_impl<CatalogueEventsWidgetPrivate>()}
{
    ui->setupUi(this);

    ui->tableView->setDragDropMode(QAbstractItemView::DragDrop);
    ui->tableView->setDragEnabled(true);

    impl->m_Model = new CatalogueEventsTableModel{this};
    ui->tableView->setModel(impl->m_Model);

    ui->tableView->setSortingEnabled(true);

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

    auto emitSelection = [this]() {
        QVector<DBEvent> events;
        for (auto rowIndex : ui->tableView->selectionModel()->selectedRows()) {
            events << impl->m_Model->getEvent(rowIndex.row());
        }

        emit this->eventsSelected(events);
    };

    connect(ui->tableView, &QTableView::clicked, emitSelection);
    connect(ui->tableView->selectionModel(), &QItemSelectionModel::selectionChanged, emitSelection);

    connect(ui->tableView->selectionModel(), &QItemSelectionModel::selectionChanged, [this]() {
        auto isNotMultiSelection = ui->tableView->selectionModel()->selectedRows().count() <= 1;
        ui->btnChart->setEnabled(isNotMultiSelection);
        ui->btnTime->setEnabled(isNotMultiSelection);
    });

    ui->tableView->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->tableView->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    ui->tableView->horizontalHeader()->setSortIndicatorShown(true);
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}

void CatalogueEventsWidget::populateWithCatalogues(const QVector<DBCatalogue> &catalogues)
{
    auto &dao = sqpApp->catalogueController().getDao();

    QSet<QUuid> eventIds;
    QVector<DBEvent> events;

    for (auto catalogue : catalogues) {
        auto catalogueEvents = dao.getCatalogueEvents(catalogue);
        for (auto event : catalogueEvents) {
            if (!eventIds.contains(event.getUniqId())) {
                events << event;
                eventIds.insert(event.getUniqId());
            }
        }
    }

    ui->tableView->setSortingEnabled(false);
    impl->m_Model->setEvents(events);
    ui->tableView->setSortingEnabled(true);
}
