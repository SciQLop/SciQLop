#include "Catalogue/CatalogueInspectorWidget.h"
#include "ui_CatalogueInspectorWidget.h"

#include <Common/DateUtils.h>
#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBTag.h>

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

void CatalogueInspectorWidget::setEvent(const DBEvent &event)
{
    showPage(Page::EventProperties);
    ui->leEventName->setText(event.getName());
    ui->leEventMission->setText(event.getMission());
    ui->leEventProduct->setText(event.getProduct());

    QString tagList;
    auto tags = const_cast<DBEvent *>(&event)->getTags();
    for (auto tag : tags) {
        tagList += tag.getName();
        tagList += ' ';
    }

    ui->leEventTags->setText(tagList);

    ui->dateTimeEventTStart->setDateTime(DateUtils::dateTime(event.getTStart()));
    ui->dateTimeEventTEnd->setDateTime(DateUtils::dateTime(event.getTEnd()));
}

void CatalogueInspectorWidget::setCatalogue(const DBCatalogue &catalogue)
{
    showPage(Page::CatalogueProperties);
    ui->leCatalogueName->setText(catalogue.getName());
    ui->leCatalogueAuthor->setText(catalogue.getAuthor());
}
