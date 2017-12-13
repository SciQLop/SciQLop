#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueEventsTableModel.h>
#include <CatalogueDao.h>
#include <DBCatalogue.h>
#include <SqpApplication.h>
#include <Visualization/VisualizationTabWidget.h>
#include <Visualization/VisualizationWidget.h>
#include <Visualization/VisualizationZoneWidget.h>

#include <QDialog>
#include <QDialogButtonBox>
#include <QListWidget>

Q_LOGGING_CATEGORY(LOG_CatalogueEventsWidget, "CatalogueEventsWidget")

/// Format of the dates appearing in the label of a cursor
const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss");

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {

    CatalogueEventsTableModel *m_Model = nullptr;
    QStringList m_ZonesForTimeMode;
    QString m_ZoneForGraphMode;

    VisualizationWidget *m_VisualizationWidget = nullptr;

    void setEvents(const QVector<std::shared_ptr<DBEvent> > &events, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->setEvents(events);
        tableView->setSortingEnabled(true);
    }

    void addEvent(const std::shared_ptr<DBEvent> &event, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->addEvent(event);
        tableView->setSortingEnabled(true);
    }

    void removeEvent(const std::shared_ptr<DBEvent> &event, QTableView *tableView)
    {
        tableView->setSortingEnabled(false);
        m_Model->removeEvent(event);
        tableView->setSortingEnabled(true);
    }

    QStringList getAvailableVisualizationZoneList() const
    {
        if (m_VisualizationWidget) {
            if (auto tab = m_VisualizationWidget->currentTabWidget()) {
                return tab->availableZoneWidgets();
            }
        }

        return QStringList{};
    }

    QStringList selectZone(QWidget *parent, const QStringList &selectedZones,
                           bool allowMultiSelection, const QPoint &location)
    {
        auto availableZones = getAvailableVisualizationZoneList();
        if (availableZones.isEmpty()) {
            return QStringList{};
        }

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
        else {
            result = selectedZones;
        }

        return result;
    }

    void updateForTimeMode(QTableView *tableView)
    {
        auto selectedRows = tableView->selectionModel()->selectedRows();

        if (selectedRows.count() == 1) {
            auto event = m_Model->getEvent(selectedRows.first().row());
            if (m_VisualizationWidget) {
                if (auto tab = m_VisualizationWidget->currentTabWidget()) {

                    for (auto zoneName : m_ZonesForTimeMode) {
                        if (auto zone = tab->getZoneWithName(zoneName)) {
                            SqpRange eventRange;
                            eventRange.m_TStart = event->getTStart();
                            eventRange.m_TEnd = event->getTEnd();
                            zone->setZoneRange(eventRange);
                        }
                    }
                }
                else {
                    qCWarning(LOG_CatalogueEventsWidget())
                        << "updateTimeZone: no tab found in the visualization";
                }
            }
            else {
                qCWarning(LOG_CatalogueEventsWidget())
                    << "updateTimeZone: visualization widget not found";
            }
        }
        else {
            qCWarning(LOG_CatalogueEventsWidget())
                << "updateTimeZone: not compatible with multiple events selected";
        }
    }

    void updateForGraphMode(QTableView *tableView)
    {
        auto selectedRows = tableView->selectionModel()->selectedRows();

        if (selectedRows.count() == 1) {
            auto event = m_Model->getEvent(selectedRows.first().row());
            if (m_VisualizationWidget) {
                if (auto tab = m_VisualizationWidget->currentTabWidget()) {
                    if (auto zone = tab->getZoneWithName(m_ZoneForGraphMode)) {
                        // TODO
                    }
                }
                else {
                    qCWarning(LOG_CatalogueEventsWidget())
                        << "updateGraphMode: no tab found in the visualization";
                }
            }
            else {
                qCWarning(LOG_CatalogueEventsWidget())
                    << "updateGraphMode: visualization widget not found";
            }
        }
        else {
            qCWarning(LOG_CatalogueEventsWidget())
                << "updateGraphMode: not compatible with multiple events selected";
        }
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
            impl->m_ZonesForTimeMode
                = impl->selectZone(this, impl->m_ZonesForTimeMode, true,
                                   this->mapToGlobal(ui->btnTime->frameGeometry().center()));

            impl->updateForTimeMode(ui->tableView);
        }
    });

    connect(ui->btnChart, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnTime->setChecked(false);
            impl->m_ZoneForGraphMode
                = impl->selectZone(this, {impl->m_ZoneForGraphMode}, false,
                                   this->mapToGlobal(ui->btnChart->frameGeometry().center()))
                      .value(0);

            impl->updateForGraphMode(ui->tableView);
        }
    });

    auto emitSelection = [this]() {
        QVector<std::shared_ptr<DBEvent> > events;
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

        if (isNotMultiSelection && ui->btnTime->isChecked()) {
            impl->updateForTimeMode(ui->tableView);
        }
        else if (isNotMultiSelection && ui->btnChart->isChecked()) {
            impl->updateForGraphMode(ui->tableView);
        }
    });

    ui->tableView->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->tableView->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    ui->tableView->horizontalHeader()->setSortIndicatorShown(true);
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}

void CatalogueEventsWidget::setVisualizationWidget(VisualizationWidget *visualization)
{
    impl->m_VisualizationWidget = visualization;
}

void CatalogueEventsWidget::populateWithCatalogues(
    const QVector<std::shared_ptr<DBCatalogue> > &catalogues)
{
    QSet<QUuid> eventIds;
    QVector<std::shared_ptr<DBEvent> > events;

    for (auto catalogue : catalogues) {
        auto catalogueEvents = sqpApp->catalogueController().retrieveEventsFromCatalogue(catalogue);
        for (auto event : catalogueEvents) {
            if (!eventIds.contains(event->getUniqId())) {
                events << event;
                eventIds.insert(event->getUniqId());
            }
        }
    }

    impl->setEvents(events, ui->tableView);
}
