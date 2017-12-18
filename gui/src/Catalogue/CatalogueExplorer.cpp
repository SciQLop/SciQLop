#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

#include <Catalogue/CatalogueActionManager.h>
#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>
#include <Visualization/VisualizationWidget.h>

#include <DBCatalogue.h>
#include <DBEvent.h>

struct CatalogueExplorer::CatalogueExplorerPrivate {
    CatalogueActionManager m_ActionManager;
};

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer),
          impl{spimpl::make_unique_impl<CatalogueExplorerPrivate>()}
{
    ui->setupUi(this);

    impl->m_ActionManager.installSelectionZoneActions();

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

    connect(ui->catalogues, &CatalogueSideBarWidget::trashSelected,
            [this]() { ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty); });

    connect(ui->catalogues, &CatalogueSideBarWidget::allEventsSelected, [this]() {
        ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty);
        ui->events->populateWithAllEvents();
    });

    connect(ui->catalogues, &CatalogueSideBarWidget::selectionCleared,
            [this]() { ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty); });

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

    connect(ui->inspector, &CatalogueInspectorWidget::catalogueUpdated, [this](auto catalogue) {
        sqpApp->catalogueController().updateCatalogue(catalogue);
        ui->catalogues->setCatalogueChanges(catalogue, true);
    });

    connect(ui->inspector, &CatalogueInspectorWidget::eventUpdated, [this](auto event) {
        sqpApp->catalogueController().updateEvent(event);
        ui->events->setEventChanges(event, true);
    });

    connect(ui->inspector, &CatalogueInspectorWidget::eventProductUpdated,
            [this](auto event, auto eventProduct) { ui->events->setEventChanges(event, true); });
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}

void CatalogueExplorer::setVisualizationWidget(VisualizationWidget *visualization)
{
    ui->events->setVisualizationWidget(visualization);
}
