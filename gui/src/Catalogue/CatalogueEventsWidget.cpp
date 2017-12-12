#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueEventsTableModel.h>
#include <CatalogueDao.h>
#include <DBCatalogue.h>
#include <SqpApplication.h>

#include <QDialog>
#include <QDialogButtonBox>
#include <QListWidget>


/// Format of the dates appearing in the label of a cursor
const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss");

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {

    CatalogueEventsTableModel *m_Model = nullptr;
    QString m_ZoneForTimeMode;
    QString m_ZoneForGraphMode;

    void setEvents(const QVector<DBEvent> &events, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->setEvents(events);
        tableView->setSortingEnabled(true);
    }

    void addEvent(const DBEvent &event, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->addEvent(event);
        tableView->setSortingEnabled(true);
    }

    void removeEvent(const DBEvent &event, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->removeEvent(event);
        tableView->setSortingEnabled(true);
    }

    QStringList selectZone(QWidget *parent, const QStringList &availableZones,
                           const QStringList &selectedZones, bool allowMultiSelection,
                           const QPoint &location)
    {
        QDialog d(parent, Qt::Tool);
        d.setWindowTitle("Choose a zone");
        auto layout = new QVBoxLayout{&d};
        layout->setContentsMargins(0, 0, 0, 0);
        auto listWidget = new QListWidget{&d};
        layout->addWidget(listWidget);

        QSet<QListWidgetItem *> checkedItems;
        for (auto zone : availableZones) {
            auto item = new QListWidgetItem{zone};
            item->setFlags(Qt::ItemIsEnabled | Qt::ItemIsUserCheckable);
            if (selectedZones.contains(zone)) {
                item->setCheckState(Qt::Checked);
                checkedItems << item;
            }
            else {
                item->setCheckState(Qt::Unchecked);
            }

            listWidget->addItem(item);
        }

        auto buttonBox = new QDialogButtonBox{QDialogButtonBox::Ok, &d};
        layout->addWidget(buttonBox);

        QObject::connect(buttonBox, &QDialogButtonBox::accepted, &d, &QDialog::accept);
        QObject::connect(buttonBox, &QDialogButtonBox::rejected, &d, &QDialog::reject);

        QObject::connect(listWidget, &QListWidget::itemChanged,
                         [&checkedItems, allowMultiSelection, listWidget](auto item) {
                             if (item->checkState() == Qt::Checked) {
                                 if (!allowMultiSelection) {
                                     for (auto checkedItem : checkedItems) {
                                         listWidget->blockSignals(true);
                                         checkedItem->setCheckState(Qt::Unchecked);
                                         listWidget->blockSignals(false);
                                     }

                                     checkedItems.clear();
                                 }
                                 checkedItems << item;
                             }
                             else {
                                 checkedItems.remove(item);
                             }
                         });

        QStringList result;

        d.setMinimumWidth(120);
        d.resize(d.minimumSizeHint());
        d.move(location);
        if (d.exec() == QDialog::Accepted) {
            for (auto item : checkedItems) {
                result += item->text();
            }
        }

        return result;
    }
};

CatalogueEventsWidget::CatalogueEventsWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueEventsWidget),
          impl{spimpl::make_unique_impl<CatalogueEventsWidgetPrivate>()}
{
    ui->setupUi(this);

    impl->m_Model = new CatalogueEventsTableModel{this};
    ui->tableView->setModel(impl->m_Model);

    ui->tableView->setSortingEnabled(true);
    ui->tableView->setDragDropMode(QAbstractItemView::DragDrop);
    ui->tableView->setDragEnabled(true);

    connect(ui->btnTime, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnChart->setChecked(false);
            impl->m_ZoneForTimeMode
                = impl->selectZone(this, {"Zone 1", "Zone 2", "Zone 3", "Zone 4"},
                                   {impl->m_ZoneForTimeMode}, false,
                                   this->mapToGlobal(ui->btnTime->frameGeometry().center()))
                      .value(0);
        }
    });

    connect(ui->btnChart, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnTime->setChecked(false);
            impl->m_ZoneForGraphMode
                = impl->selectZone(this, {"Zone 1", "Zone 2", "Zone 3", "Zone 4"},
                                   {impl->m_ZoneForGraphMode}, false,
                                   this->mapToGlobal(ui->btnChart->frameGeometry().center()))
                      .value(0);
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

    impl->setEvents(events, ui->tableView);
}
