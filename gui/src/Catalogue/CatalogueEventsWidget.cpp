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

    impl->m_Model = new CatalogueEventsTableModel(this);
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

    connect(ui->tableView, &QTableView::clicked, [this](auto index) {
        auto event = impl->m_Model->getEvent(index.row());
        emit this->eventSelected(event);
    });

    connect(ui->tableView->selectionModel(), &QItemSelectionModel::currentChanged,
            [this](auto current, auto previous) {
                if (current.isValid() && current.row() >= 0) {
                    auto event = impl->m_Model->getEvent(current.row());
                    emit this->eventSelected(event);
                }
            });

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

void CatalogueEventsWidget::populateWithCatalogue(const DBCatalogue &catalogue)
{
    auto &dao = sqpApp->catalogueController().getDao();
    auto events = dao.getCatalogueEvents(catalogue);

    QVector<DBEvent> eventVector;
    for (auto event : events) {
        eventVector << event;
    }

    ui->tableView->setSortingEnabled(false);
    impl->m_Model->setEvents(eventVector);
    ui->tableView->setSortingEnabled(true);
}
