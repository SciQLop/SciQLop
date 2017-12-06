#include "Catalogue/CatalogueEventsWidget.h"
#include "ui_CatalogueEventsWidget.h"

CatalogueEventsWidget::CatalogueEventsWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::CatalogueEventsWidget)
{
    ui->setupUi(this);
}

CatalogueEventsWidget::~CatalogueEventsWidget()
{
    delete ui;
}
