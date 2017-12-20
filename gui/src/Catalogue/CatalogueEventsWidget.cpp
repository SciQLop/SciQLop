#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueEventsModel.h>
#include <Catalogue/CatalogueExplorerHelper.h>
#include <CatalogueDao.h>
#include <DBCatalogue.h>
#include <SqpApplication.h>
#include <Visualization/VisualizationTabWidget.h>
#include <Visualization/VisualizationWidget.h>
#include <Visualization/VisualizationZoneWidget.h>

#include <QDialog>
#include <QDialogButtonBox>
#include <QListWidget>
#include <QMessageBox>

Q_LOGGING_CATEGORY(LOG_CatalogueEventsWidget, "CatalogueEventsWidget")

/// Fixed size of the validation column
const auto VALIDATION_COLUMN_SIZE = 35;

struct CatalogueEventsWidget::CatalogueEventsWidgetPrivate {

    CatalogueEventsModel *m_Model = nullptr;
    QStringList m_ZonesForTimeMode;
    QString m_ZoneForGraphMode;
    QVector<std::shared_ptr<DBCatalogue> > m_DisplayedCatalogues;

    VisualizationWidget *m_VisualizationWidget = nullptr;

    void setEvents(const QVector<std::shared_ptr<DBEvent> > &events, CatalogueEventsWidget *widget)
    {
        widget->ui->treeView->setSortingEnabled(false);
        m_Model->setEvents(events);
        widget->ui->treeView->setSortingEnabled(true);

        for (auto event : events) {
            if (sqpApp->catalogueController().eventHasChanges(event)) {
                auto index = m_Model->indexOf(event);
                widget->setEventChanges(event, true);
            }
        }
    }

    void addEvent(const std::shared_ptr<DBEvent> &event, QTreeView *treeView)
    {
        treeView->setSortingEnabled(false);
        m_Model->addEvent(event);
        treeView->setSortingEnabled(true);
    }

    void removeEvent(const std::shared_ptr<DBEvent> &event, QTreeView *treeView)
    {
        treeView->setSortingEnabled(false);
        m_Model->removeEvent(event);
        treeView->setSortingEnabled(true);
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

    void updateForTimeMode(QTreeView *treeView)
    {
        auto selectedRows = treeView->selectionModel()->selectedRows();

        if (selectedRows.count() == 1) {
            auto event = m_Model->getEvent(selectedRows.first());
            if (event) {
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
        }
        else {
            qCWarning(LOG_CatalogueEventsWidget())
                << "updateTimeZone: not compatible with multiple events selected";
        }
    }

    void updateForGraphMode(QTreeView *treeView)
    {
        auto selectedRows = treeView->selectionModel()->selectedRows();

        if (selectedRows.count() == 1) {
            auto event = m_Model->getEvent(selectedRows.first());
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

    void getSelectedItems(
        QTreeView *treeView, QVector<std::shared_ptr<DBEvent> > &events,
        QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > > &eventProducts)
    {
        for (auto rowIndex : treeView->selectionModel()->selectedRows()) {
            auto itemType = m_Model->itemTypeOf(rowIndex);
            if (itemType == CatalogueEventsModel::ItemType::Event) {
                events << m_Model->getEvent(rowIndex);
            }
            else if (itemType == CatalogueEventsModel::ItemType::EventProduct) {
                eventProducts << qMakePair(m_Model->getParentEvent(rowIndex),
                                           m_Model->getEventProduct(rowIndex));
            }
        }
    }
};

CatalogueEventsWidget::CatalogueEventsWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueEventsWidget),
          impl{spimpl::make_unique_impl<CatalogueEventsWidgetPrivate>()}
{
    ui->setupUi(this);

    impl->m_Model = new CatalogueEventsModel{this};
    ui->treeView->setModel(impl->m_Model);

    ui->treeView->setSortingEnabled(true);
    ui->treeView->setDragDropMode(QAbstractItemView::DragDrop);
    ui->treeView->setDragEnabled(true);

    connect(ui->btnTime, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnChart->setChecked(false);
            impl->m_ZonesForTimeMode
                = impl->selectZone(this, impl->m_ZonesForTimeMode, true,
                                   this->mapToGlobal(ui->btnTime->frameGeometry().center()));

            impl->updateForTimeMode(ui->treeView);
        }
    });

    connect(ui->btnChart, &QToolButton::clicked, [this](auto checked) {
        if (checked) {
            ui->btnTime->setChecked(false);
            impl->m_ZoneForGraphMode
                = impl->selectZone(this, {impl->m_ZoneForGraphMode}, false,
                                   this->mapToGlobal(ui->btnChart->frameGeometry().center()))
                      .value(0);

            impl->updateForGraphMode(ui->treeView);
        }
    });

    connect(ui->btnRemove, &QToolButton::clicked, [this]() {
        QVector<std::shared_ptr<DBEvent> > events;
        QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > > eventProducts;
        impl->getSelectedItems(ui->treeView, events, eventProducts);

        if (!events.isEmpty() && eventProducts.isEmpty()) {

            if (QMessageBox::warning(this, tr("Remove Event(s)"),
                                     tr("The selected event(s) will be completly removed "
                                        "from the repository!\nAre you sure you want to continue?"),
                                     QMessageBox::Yes | QMessageBox::No, QMessageBox::No)
                == QMessageBox::Yes) {

                for (auto event : events) {
                    sqpApp->catalogueController().removeEvent(event);
                    impl->removeEvent(event, ui->treeView);
                }
            }
        }
    });

    connect(ui->treeView, &QTreeView::clicked, this, &CatalogueEventsWidget::emitSelection);
    connect(ui->treeView->selectionModel(), &QItemSelectionModel::selectionChanged, this,
            &CatalogueEventsWidget::emitSelection);

    ui->btnRemove->setEnabled(false); // Disabled by default when nothing is selected
    connect(ui->treeView->selectionModel(), &QItemSelectionModel::selectionChanged, [this]() {
        auto isNotMultiSelection = ui->treeView->selectionModel()->selectedRows().count() <= 1;
        ui->btnChart->setEnabled(isNotMultiSelection);
        ui->btnTime->setEnabled(isNotMultiSelection);

        if (isNotMultiSelection && ui->btnTime->isChecked()) {
            impl->updateForTimeMode(ui->treeView);
        }
        else if (isNotMultiSelection && ui->btnChart->isChecked()) {
            impl->updateForGraphMode(ui->treeView);
        }

        QVector<std::shared_ptr<DBEvent> > events;
        QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > > eventProducts;
        impl->getSelectedItems(ui->treeView, events, eventProducts);
        ui->btnRemove->setEnabled(!events.isEmpty() && eventProducts.isEmpty());
    });

    ui->treeView->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->treeView->header()->setSectionResizeMode((int)CatalogueEventsModel::Column::Tags,
                                                 QHeaderView::Stretch);
    ui->treeView->header()->setSectionResizeMode((int)CatalogueEventsModel::Column::Validation,
                                                 QHeaderView::Fixed);
    ui->treeView->header()->setSectionResizeMode((int)CatalogueEventsModel::Column::Name,
                                                 QHeaderView::Interactive);
    ui->treeView->header()->resizeSection((int)CatalogueEventsModel::Column::Validation,
                                          VALIDATION_COLUMN_SIZE);
    ui->treeView->header()->setSortIndicatorShown(true);

    connect(impl->m_Model, &CatalogueEventsModel::modelSorted, [this]() {
        auto allEvents = impl->m_Model->events();
        for (auto event : allEvents) {
            setEventChanges(event, sqpApp->catalogueController().eventHasChanges(event));
        }
    });

    populateWithAllEvents();
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}

void CatalogueEventsWidget::setVisualizationWidget(VisualizationWidget *visualization)
{
    impl->m_VisualizationWidget = visualization;
}

void CatalogueEventsWidget::addEvent(const std::shared_ptr<DBEvent> &event)
{
    impl->addEvent(event, ui->treeView);
}

void CatalogueEventsWidget::setEventChanges(const std::shared_ptr<DBEvent> &event, bool hasChanges)
{
    impl->m_Model->refreshEvent(event);

    auto eventIndex = impl->m_Model->indexOf(event);
    auto validationIndex
        = eventIndex.sibling(eventIndex.row(), (int)CatalogueEventsModel::Column::Validation);

    if (validationIndex.isValid()) {
        if (hasChanges) {
            if (ui->treeView->indexWidget(validationIndex) == nullptr) {
                auto widget = CatalogueExplorerHelper::buildValidationWidget(
                    ui->treeView,
                    [this, event]() {
                        sqpApp->catalogueController().saveEvent(event);
                        setEventChanges(event, false);
                    },
                    [this, event]() {
                        sqpApp->catalogueController().discardEvent(event);
                        setEventChanges(event, false);
                        impl->m_Model->refreshEvent(event, true);
                        emitSelection();
                    });
                ui->treeView->setIndexWidget(validationIndex, widget);
            }
        }
        else {
            // Note: the widget is destroyed
            ui->treeView->setIndexWidget(validationIndex, nullptr);
        }
    }
    else {
        qCWarning(LOG_CatalogueEventsWidget())
            << "setEventChanges: the event is not displayed in the model.";
    }
}

QVector<std::shared_ptr<DBCatalogue> > CatalogueEventsWidget::displayedCatalogues() const
{
    return impl->m_DisplayedCatalogues;
}

bool CatalogueEventsWidget::isAllEventsDisplayed() const
{
    return impl->m_DisplayedCatalogues.isEmpty() && !impl->m_Model->events().isEmpty();
}

bool CatalogueEventsWidget::isEventDisplayed(const std::shared_ptr<DBEvent> &event) const
{
    return impl->m_Model->indexOf(event).isValid();
}

void CatalogueEventsWidget::populateWithCatalogues(
    const QVector<std::shared_ptr<DBCatalogue> > &catalogues)
{
    impl->m_DisplayedCatalogues = catalogues;

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

    impl->setEvents(events, this);
}

void CatalogueEventsWidget::populateWithAllEvents()
{
    impl->m_DisplayedCatalogues.clear();

    auto allEvents = sqpApp->catalogueController().retrieveAllEvents();

    QVector<std::shared_ptr<DBEvent> > events;
    for (auto event : allEvents) {
        events << event;
    }

    impl->setEvents(events, this);
}

void CatalogueEventsWidget::clear()
{
    impl->m_DisplayedCatalogues.clear();
    impl->setEvents({}, this);
}

void CatalogueEventsWidget::refresh()
{
    if (impl->m_DisplayedCatalogues.isEmpty()) {
        populateWithAllEvents();
    }
    else {
        populateWithCatalogues(impl->m_DisplayedCatalogues);
    }
}

void CatalogueEventsWidget::emitSelection()
{
    QVector<std::shared_ptr<DBEvent> > events;
    QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > > eventProducts;
    impl->getSelectedItems(ui->treeView, events, eventProducts);

    if (!events.isEmpty() && eventProducts.isEmpty()) {
        emit eventsSelected(events);
    }
    else if (events.isEmpty() && !eventProducts.isEmpty()) {
        emit eventProductsSelected(eventProducts);
    }
    else {
        emit selectionCleared();
    }
}
