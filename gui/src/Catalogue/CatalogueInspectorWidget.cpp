#include "Catalogue/CatalogueInspectorWidget.h"
#include "ui_CatalogueInspectorWidget.h"

CatalogueInspectorWidget::CatalogueInspectorWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::CatalogueInspectorWidget)
{
    ui->setupUi(this);
}

CatalogueInspectorWidget::~CatalogueInspectorWidget()
{
    delete ui;
}
