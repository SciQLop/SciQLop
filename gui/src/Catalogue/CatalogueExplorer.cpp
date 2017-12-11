#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

#include <DBCatalogue.h>
#include <DBEvent.h>

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer)
{
    ui->setupUi(this);

    connect(ui->catalogues, &CatalogueSideBarWidget::catalogueSelected, [this](auto catalogue) {
        ui->inspector->setCatalogue(catalogue);
        ui->events->populateWithCatalogue(catalogue);
    });

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
