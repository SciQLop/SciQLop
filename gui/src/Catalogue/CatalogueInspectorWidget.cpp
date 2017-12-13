#include "Catalogue/CatalogueInspectorWidget.h"
#include "ui_CatalogueInspectorWidget.h"

CatalogueInspectorWidget::CatalogueInspectorWidget(QWidget *parent)
        : QWidget(parent), ui(new Ui::CatalogueInspectorWidget)
{
    ui->setupUi(this);
    showPage(Page::Empty);
}

CatalogueInspectorWidget::~CatalogueInspectorWidget()
{
    delete ui;
}

void CatalogueInspectorWidget::showPage(CatalogueInspectorWidget::Page page)
{
    ui->stackedWidget->setCurrentIndex(static_cast<int>(page));
}

CatalogueInspectorWidget::Page CatalogueInspectorWidget::currentPage() const
{
    return static_cast<Page>(ui->stackedWidget->currentIndex());
}

void CatalogueInspectorWidget::setEvent(const QString &event)
{
    showPage(Page::EventProperties);
    ui->leEventName->setText(event);
}

void CatalogueInspectorWidget::setCatalogue(const QString &catalogue)
{
    showPage(Page::CatalogueProperties);
    ui->leCatalogueName->setText(catalogue);
}