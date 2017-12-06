#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent), ui(new Ui::CatalogueExplorer)
{
    ui->setupUi(this);
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}
