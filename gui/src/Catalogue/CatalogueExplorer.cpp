#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

#include <Catalogue/CatalogueActionManager.h>
#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>
#include <Visualization/VisualizationGraphWidget.h>
#include <Visualization/VisualizationSelectionZoneItem.h>
#include <Visualization/VisualizationWidget.h>

#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBEventProduct.h>

#include <unordered_map>

struct CatalogueExplorer::CatalogueExplorerPrivate {
    CatalogueActionManager m_ActionManager;
    std::unordered_map<std::shared_ptr<DBEvent>, QVector<VisualizationSelectionZoneItem *> >
        m_SelectionZonesPerEvents;

    QMetaObject::Connection m_Conn;

    CatalogueExplorerPrivate(CatalogueExplorer *catalogueExplorer)
            : m_ActionManager(catalogueExplorer)
    {
    }
};

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer),
          impl{spimpl::make_unique_impl<CatalogueExplorerPrivate>(this)}
{
    ui->setupUi(this);

    impl->m_ActionManager.installSelectionZoneActions();

    // Updates events and inspector when something is selected in the catalogue widget
    connect(ui->catalogues, &CatalogueSideBarWidget::catalogueSelected, [this](auto catalogues) {
        if (catalogues.count() == 1) {
            ui->inspector->setCatalogue(catalogues.first());
        }
        else {
            ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        }

        ui->events->populateWithCatalogues(catalogues);
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::databaseSelected, [this](auto databases) {
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::trashSelected, [this]() {
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        ui->events->clear();
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::allEventsSelected, [this]() {
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        ui->events->populateWithAllEvents();
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::databaseSelected, [this](auto databaseList) {
        QVector<std::shared_ptr<DBCatalogue> > catalogueList;
        for (auto database : databaseList) {
            catalogueList.append(ui->catalogues->getCatalogues(database));
        }
        ui->events->populateWithCatalogues(catalogueList);
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::selectionCleared, [this]() {
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        ui->events->clear();
    });

    // Updates the inspectot when something is selected in the events
    connect(ui->events, &CatalogueEventsWidget::eventsSelected, [this](auto events) {
        if (events.count() == 1) {
            ui->inspector->setEvent(events.first());
        }
        else {
            ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        }
    });

    connect(ui->events, &CatalogueEventsWidget::eventProductsSelected, [this](auto eventProducts) {
        if (eventProducts.count() == 1) {
            ui->inspector->setEventProduct(eventProducts.first().first,
                                           eventProducts.first().second);
        }
        else {
            ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        }
    });

    connect(ui->events, &CatalogueEventsWidget::selectionCleared,
            [this]() { ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty); });

    // Manage Selection Zones associated to events
    connect(ui->events, &CatalogueEventsWidget::selectionZoneAdded,
            [this](auto event, auto productId, auto zone) {
                this->addSelectionZoneItem(event, productId, zone);
            });

    connect(ui->events, &CatalogueEventsWidget::eventsRemoved, [this](auto events) {
        for (auto event : events) {
            auto associatedSelectionZonesIt = impl->m_SelectionZonesPerEvents.find(event);
            if (associatedSelectionZonesIt != impl->m_SelectionZonesPerEvents.cend()) {
                for (auto selectionZone : associatedSelectionZonesIt->second) {
                    auto parentGraph = selectionZone->parentGraphWidget();
                    parentGraph->removeSelectionZone(selectionZone);
                }

                impl->m_SelectionZonesPerEvents.erase(event);
            }
        }
    });

    // Updates changes from the inspector
    connect(ui->inspector, &CatalogueInspectorWidget::catalogueUpdated, [this](auto catalogue) {
        sqpApp->catalogueController().updateCatalogue(catalogue);
        ui->catalogues->setCatalogueChanges(catalogue, true);
    });

    connect(ui->inspector, &CatalogueInspectorWidget::eventUpdated, [this](auto event) {
        sqpApp->catalogueController().updateEvent(event);
        ui->events->setEventChanges(event, true);
    });

    connect(ui->inspector, &CatalogueInspectorWidget::eventProductUpdated,
            [this](auto event, auto eventProduct) {
                sqpApp->catalogueController().updateEventProduct(eventProduct);
                ui->events->setEventChanges(event, true);
            });

    connect(ui->events, &CatalogueEventsWidget::eventCataloguesModified,
            [this](const QVector<std::shared_ptr<DBCatalogue> > &catalogues) {
                for (auto catalogue : catalogues) {
                    ui->catalogues->setCatalogueChanges(catalogue, true);
                }
            });
}

CatalogueExplorer::~CatalogueExplorer()
{
    disconnect(impl->m_Conn);
    delete ui;
}

void CatalogueExplorer::setVisualizationWidget(VisualizationWidget *visualization)
{
    ui->events->setVisualizationWidget(visualization);
}

CatalogueEventsWidget &CatalogueExplorer::eventsWidget() const
{
    return *ui->events;
}

CatalogueSideBarWidget &CatalogueExplorer::sideBarWidget() const
{
    return *ui->catalogues;
}

void CatalogueExplorer::clearSelectionZones()
{
    impl->m_SelectionZonesPerEvents.clear();
}

void CatalogueExplorer::addSelectionZoneItem(const std::shared_ptr<DBEvent> &event,
                                             const QString &productId,
                                             VisualizationSelectionZoneItem *selectionZone)
{
    impl->m_SelectionZonesPerEvents[event] << selectionZone;
    connect(selectionZone, &VisualizationSelectionZoneItem::rangeEdited,
            [event, productId, this](auto range) {
                auto productList = event->getEventProducts();
                for (auto &product : productList) {
                    if (product.getProductId() == productId) {
                        product.setTStart(range.m_TStart);
                        product.setTEnd(range.m_TEnd);
                    }
                }
                event->setEventProducts(productList);
                sqpApp->catalogueController().updateEvent(event);
                ui->events->refreshEvent(event);
                ui->events->setEventChanges(event, true);
                ui->inspector->refresh();
            });

    impl->m_Conn = connect(selectionZone, &VisualizationSelectionZoneItem::destroyed,
                           [event, selectionZone, this]() {
                               if (!impl->m_SelectionZonesPerEvents.empty()) {
                                   impl->m_SelectionZonesPerEvents[event].removeAll(selectionZone);
                               }
                           });
}
