#include "Catalogue/CatalogueInspectorWidget.h"
#include "ui_CatalogueInspectorWidget.h"

#include <Common/DateUtils.h>
#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBTag.h>

struct CatalogueInspectorWidget::CatalogueInspectorWidgetPrivate {
    std::shared_ptr<DBCatalogue> m_DisplayedCatalogue = nullptr;
    std::shared_ptr<DBEvent> m_DisplayedEvent = nullptr;
};

CatalogueInspectorWidget::CatalogueInspectorWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueInspectorWidget),
          impl{spimpl::make_unique_impl<CatalogueInspectorWidgetPrivate>()}
{
    ui->setupUi(this);
    showPage(Page::Empty);

    connect(ui->leCatalogueName, &QLineEdit::editingFinished, [this]() {
        if (ui->leCatalogueName->text() != impl->m_DisplayedCatalogue->getName()) {
            impl->m_DisplayedCatalogue->setName(ui->leCatalogueName->text());
            emit this->catalogueUpdated(impl->m_DisplayedCatalogue);
        }
    });

    connect(ui->leCatalogueAuthor, &QLineEdit::editingFinished, [this]() {
        if (ui->leCatalogueAuthor->text() != impl->m_DisplayedCatalogue->getAuthor()) {
            impl->m_DisplayedCatalogue->setAuthor(ui->leCatalogueAuthor->text());
            emit this->catalogueUpdated(impl->m_DisplayedCatalogue);
        }
    });
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

void CatalogueInspectorWidget::setEvent(const std::shared_ptr<DBEvent> &event)
{
    impl->m_DisplayedEvent = event;

    blockSignals(true);

    showPage(Page::EventProperties);
    ui->leEventName->setText(event->getName());
    ui->leEventMission->setText(event->getMission());
    ui->leEventProduct->setText(event->getProduct());

    QString tagList;
    auto tags = event->getTags();
    for (auto tag : tags) {
        tagList += tag.getName();
        tagList += ' ';
    }

    ui->leEventTags->setText(tagList);

    ui->dateTimeEventTStart->setDateTime(DateUtils::dateTime(event->getTStart()));
    ui->dateTimeEventTEnd->setDateTime(DateUtils::dateTime(event->getTEnd()));

    blockSignals(false);
}

void CatalogueInspectorWidget::setCatalogue(const std::shared_ptr<DBCatalogue> &catalogue)
{
    impl->m_DisplayedCatalogue = catalogue;

    blockSignals(true);

    showPage(Page::CatalogueProperties);
    ui->leCatalogueName->setText(catalogue->getName());
    ui->leCatalogueAuthor->setText(catalogue->getAuthor());

    blockSignals(false);
}
