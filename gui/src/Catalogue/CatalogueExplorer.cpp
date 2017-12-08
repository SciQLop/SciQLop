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

    connect(ui->events, &CatalogueEventsWidget::eventSelected,
            [this](auto event) { ui->inspector->setEvent(event); });
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}
