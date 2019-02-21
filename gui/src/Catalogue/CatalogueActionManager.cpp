#include "Catalogue/CatalogueActionManager.h"

#include <Actions/ActionsGuiController.h>
#include <Catalogue/CatalogueController.h>
#include <DataSource/DataSourceItem.h>
#include <SqpApplication.h>
#include <Variable/Variable.h>
#include <Visualization/VisualizationGraphWidget.h>
#include <Visualization/VisualizationSelectionZoneItem.h>

#include <Catalogue/CatalogueEventsWidget.h>
#include <Catalogue/CatalogueExplorer.h>
#include <Catalogue/CatalogueSideBarWidget.h>

//#include <CatalogueDao.h>
//#include <DBCatalogue.h>
//#include <DBEvent.h>
//#include <DBEventProduct.h>

#include <Catalogue/CatalogueController.h>
#include <Event.hpp>

#include <QBoxLayout>
#include <QComboBox>
#include <QDialog>
#include <QDialogButtonBox>
#include <QLineEdit>
#include <memory>

const auto CATALOGUE_MENU_NAME = QObject::tr("Catalogues");
const auto CATALOGUE_CREATE_EVENT_MENU_NAME = QObject::tr("New Event...");

const auto DEFAULT_EVENT_NAME = QObject::tr("Event");
const auto DEFAULT_CATALOGUE_NAME = QObject::tr("Catalogue");

struct CatalogueActionManager::CatalogueActionManagerPrivate
{

    CatalogueExplorer* m_CatalogueExplorer = nullptr;
    QVector<std::shared_ptr<SelectionZoneAction>> m_CreateInCatalogueActions;

    CatalogueActionManagerPrivate(CatalogueExplorer* catalogueExplorer)
            : m_CatalogueExplorer(catalogueExplorer)
    {
    }

    void createEventFromZones(const QString& eventName,
        const QVector<VisualizationSelectionZoneItem*>& zones,
        const CatalogueController::Catalogue_ptr& catalogue = nullptr)
    {
        auto event = CatalogueController::make_event_ptr();
        event->name = eventName.toStdString();

        // std::list<DBEventProduct> productList;
        for (auto zone : zones)
        {
            auto graph = zone->parentGraphWidget();
            for (auto var : graph->variables())
            {

                auto eventProduct = CatalogueController::Product_t();
                auto productId
                    = var->metadata().value(DataSourceItem::ID_DATA_KEY, "UnknownID").toString();

                auto zoneRange = zone->range();
                eventProduct.startTime = zoneRange.m_TStart;
                eventProduct.stopTime = zoneRange.m_TEnd;

                eventProduct.name = productId.toStdString();
                event->products.push_back(std::move(eventProduct));
            }
        }

        sqpApp->catalogueController().add(event);


        if (catalogue)
        {
            catalogue->add(event);
            // TODO use notifications
            // this shouldn't know GUI stuff and care about which widget to update
            // sqpApp->catalogueController().updateCatalogue(catalogue);
            //            m_CatalogueExplorer->sideBarWidget().setCatalogueChanges(catalogue, true);
            //            if
            //            (m_CatalogueExplorer->eventsWidget().displayedCatalogues().contains(catalogue))
            //            {
            //                m_CatalogueExplorer->eventsWidget().addEvent(event);
            //                m_CatalogueExplorer->eventsWidget().setEventChanges(event, true);
            //            }
        }
        else if (m_CatalogueExplorer->eventsWidget().isAllEventsDisplayed())
        {
            // m_CatalogueExplorer->eventsWidget().addEvent(event);
            // m_CatalogueExplorer->eventsWidget().setEventChanges(event, true);
        }
    }

    SelectionZoneAction::EnableFunction createEventEnableFuntion() const
    {
        return [](auto zones) {
            // Checks that all variables in the zones doesn't refer to the same product
            QSet<QString> usedDatasource;
            for (auto zone : zones)
            {
                auto graph = zone->parentGraphWidget();
                auto variables = graph->variables();

                for (auto var : variables)
                {
                    auto datasourceId
                        = var->metadata().value(DataSourceItem::ID_DATA_KEY).toString();
                    if (!usedDatasource.contains(datasourceId))
                    {
                        usedDatasource.insert(datasourceId);
                    }
                    else
                    {
                        return false;
                    }
                }
            }

            return true;
        };
    }
};

CatalogueActionManager::CatalogueActionManager(CatalogueExplorer* catalogueExplorer)
        : impl { spimpl::make_unique_impl<CatalogueActionManagerPrivate>(catalogueExplorer) }
{
}

void CatalogueActionManager::installSelectionZoneActions()
{
    //    auto &actionController = sqpApp->actionsGuiController();

    //    auto createEventAction = actionController.addSectionZoneAction(
    //        {CATALOGUE_MENU_NAME, CATALOGUE_CREATE_EVENT_MENU_NAME}, QObject::tr("Without
    //        Catalogue"), [this](auto zones) { impl->createEventFromZones(DEFAULT_EVENT_NAME,
    //        zones); });
    //    createEventAction->setEnableFunction(impl->createEventEnableFuntion());
    //    createEventAction->setAllowedFiltering(false);

    //    auto createEventInNewCatalogueAction = actionController.addSectionZoneAction(
    //        {CATALOGUE_MENU_NAME, CATALOGUE_CREATE_EVENT_MENU_NAME}, QObject::tr("In New
    //        Catalogue"), [this](auto zones) {

    //            auto newCatalogue = std::make_shared<DBCatalogue>();
    //            newCatalogue->setName(DEFAULT_CATALOGUE_NAME);
    //            sqpApp->catalogueController().addCatalogue(newCatalogue);
    //            impl->m_CatalogueExplorer->sideBarWidget().addCatalogue(newCatalogue,
    //                                                                    REPOSITORY_DEFAULT);

    //            impl->createEventFromZones(DEFAULT_EVENT_NAME, zones, newCatalogue);
    //        });
    //    createEventInNewCatalogueAction->setEnableFunction(impl->createEventEnableFuntion());
    //    createEventInNewCatalogueAction->setAllowedFiltering(false);

    //    refreshCreateInCatalogueAction();

    //    actionController.addFilterForMenu({CATALOGUE_MENU_NAME,
    //    CATALOGUE_CREATE_EVENT_MENU_NAME});
}

void CatalogueActionManager::refreshCreateInCatalogueAction()
{
    //    auto& actionController = sqpApp->actionsGuiController();

    //    for (auto action : impl->m_CreateInCatalogueActions)
    //    {
    //        actionController.removeAction(action);
    //    }
    //    impl->m_CreateInCatalogueActions.clear();

    //    auto allCatalogues
    //        = impl->m_CatalogueExplorer->sideBarWidget().getCatalogues(REPOSITORY_DEFAULT);

    //    for (auto catalogue : allCatalogues)
    //    {
    //        auto catalogueName = catalogue->getName();
    //        auto createEventInCatalogueAction = actionController.addSectionZoneAction(
    //            { CATALOGUE_MENU_NAME, CATALOGUE_CREATE_EVENT_MENU_NAME },
    //            QObject::tr("In \"").append(catalogueName).append("\""), [this, catalogue](auto
    //            zones) {
    //                impl->createEventFromZones(DEFAULT_EVENT_NAME, zones, catalogue);
    //            });
    //        createEventInCatalogueAction->setEnableFunction(impl->createEventEnableFuntion());
    //        impl->m_CreateInCatalogueActions << createEventInCatalogueAction;
    //    }
}
