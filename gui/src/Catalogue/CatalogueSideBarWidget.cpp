#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"

CatalogueSideBarWidget::CatalogueSideBarWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::CatalogueSideBarWidget)
{
    ui->setupUi(this);
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
}
