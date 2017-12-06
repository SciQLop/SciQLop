#include "Catalogue/CatalogueExplorer.h"
#include "ui_CatalogueExplorer.h"

CatalogueExplorer::CatalogueExplorer(QWidget *parent)
        : QDialog(parent, Qt::Dialog | Qt::WindowMinMaxButtonsHint | Qt::WindowCloseButtonHint),
          ui(new Ui::CatalogueExplorer)
{
    ui->setupUi(this);
}

CatalogueExplorer::~CatalogueExplorer()
{
    delete ui;
}
