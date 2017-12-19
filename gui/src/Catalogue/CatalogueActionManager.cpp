#include "Catalogue/CatalogueActionManager.h"

#include <Actions/ActionsGuiController.h>
#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>
#include <Variable/Variable.h>
#include <Visualization/VisualizationGraphWidget.h>
#include <Visualization/VisualizationSelectionZoneItem.h>

#include <Catalogue/CatalogueEventsWidget.h>
#include <Catalogue/CatalogueExplorer.h>
#include <Catalogue/CatalogueSideBarWidget.h>
#include <Catalogue/CreateEventDialog.h>

#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBEventProduct.h>

#include <QBoxLayout>
#include <QComboBox>
#include <QDialog>
#include <QDialogButtonBox>
#include <QLineEdit>
#include <memory>

struct CatalogueActionManager::CatalogueActionManagerPrivate {

    CatalogueExplorer *m_CatalogueExplorer = nullptr;

    CatalogueActionManagerPrivate(CatalogueExplorer *catalogueExplorer)
            : m_CatalogueExplorer(catalogueExplorer)
    {
    }

    void createEventFromZones(const QString &eventName,
                              const QVector<VisualizationSelectionZoneItem *> &zones,
                              const std::shared_ptr<DBCatalogue> &catalogue = nullptr)
    {
        auto event = std::make_shared<DBEvent>();
        event->setName(eventName);

        std::list<DBEventProduct> productList;
        for (auto zone : zones) {
            auto graph = zone->parentGraphWidget();
            for (auto var : graph->variables()) {
                auto eventProduct = std::make_shared<DBEventProduct>();
                eventProduct->setEvent(*event);

                auto zoneRange = zone->range();
                eventProduct->setTStart(zoneRange.m_TStart);
                eventProduct->setTEnd(zoneRange.m_TEnd);

                eventProduct->setProductId(var->metadata().value("id", "TODO").toString()); // todo

                productList.push_back(*eventProduct);
            }
        }

        event->setEventProducts(productList);

        sqpApp->catalogueController().addEvent(event);


        if (catalogue) {
            // TODO
            // catalogue->addEvent(event);
            m_CatalogueExplorer->sideBarWidget().setCatalogueChanges(catalogue, true);
            if (m_CatalogueExplorer->eventsWidget().displayedCatalogues().contains(catalogue)) {
                m_CatalogueExplorer->eventsWidget().addEvent(event);
                m_CatalogueExplorer->eventsWidget().setEventChanges(event, true);
            }
        }
        else if (m_CatalogueExplorer->eventsWidget().isAllEventsDisplayed()) {
            m_CatalogueExplorer->eventsWidget().addEvent(event);
            m_CatalogueExplorer->eventsWidget().setEventChanges(event, true);
        }
    }
};

CatalogueActionManager::CatalogueActionManager(CatalogueExplorer *catalogueExplorer)
        : impl{spimpl::make_unique_impl<CatalogueActionManagerPrivate>(catalogueExplorer)}
{
}

void CatalogueActionManager::installSelectionZoneActions()
{
    auto &actionController = sqpApp->actionsGuiController();

    auto createEventEnableFuntion = [](auto zones) {
        QSet<VisualizationGraphWidget *> usedGraphs;
        for (auto zone : zones) {
            auto graph = zone->parentGraphWidget();
            if (!usedGraphs.contains(graph)) {
                usedGraphs.insert(graph);
            }
            else {
                return false;
            }
        }

        return true;
    };

    auto createEventAction = actionController.addSectionZoneAction(
        {QObject::tr("Catalogues")}, QObject::tr("New Event..."), [this](auto zones) {
            CreateEventDialog dialog(
                impl->m_CatalogueExplorer->sideBarWidget().getCatalogues("Default"));
            dialog.hideCatalogueChoice();
            if (dialog.exec() == QDialog::Accepted) {
                impl->createEventFromZones(dialog.eventName(), zones);
            }
        });
    createEventAction->setEnableFunction(createEventEnableFuntion);

    auto createEventInCatalogueAction = actionController.addSectionZoneAction(
        {QObject::tr("Catalogues")}, QObject::tr("New Event in Catalogue..."), [this](auto zones) {
            CreateEventDialog dialog(
                impl->m_CatalogueExplorer->sideBarWidget().getCatalogues("Default"));
            if (dialog.exec() == QDialog::Accepted) {
                auto selectedCatalogue = dialog.selectedCatalogue();
                if (!selectedCatalogue) {
                    selectedCatalogue = std::make_shared<DBCatalogue>();
                    selectedCatalogue->setName(dialog.catalogueName());
                    // sqpApp->catalogueController().addCatalogue(selectedCatalogue); TODO
                    impl->m_CatalogueExplorer->sideBarWidget().addCatalogue(selectedCatalogue,
                                                                            "Default");
                }

                impl->createEventFromZones(dialog.eventName(), zones, selectedCatalogue);
            }
        });
    createEventInCatalogueAction->setEnableFunction(createEventEnableFuntion);
}
