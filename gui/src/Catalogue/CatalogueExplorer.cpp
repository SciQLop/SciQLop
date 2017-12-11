#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

#include <DBCatalogue.h>
#include <DBEvent.h>

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer)
{
    ui->setupUi(this);

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

    connect(ui->catalogues, &CatalogueSideBarWidget::allEventsSelected,
            [this]() { ui->inspector->showPage(CatalogueInspectorWidget::Page::Empty); });

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
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}
