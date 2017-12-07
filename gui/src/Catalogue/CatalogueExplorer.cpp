#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer)
{
    ui->setupUi(this);

    connect(ui->catalogues, &CatalogueSideBarWidget::catalogueSelected, [this](auto name) {
        ui->inspector->setEvent(name);
        ui->events->populateWithCatalogue(name);
    });

    connect(ui->events, &CatalogueEventsWidget::eventSelected,
            [this](auto name) { ui->inspector->setCatalogue(name); });
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}
