#include "Catalogue/CatalogueInspectorWidget.h"
#include "ui_CatalogueInspectorWidget.h"

#include <Common/DateUtils.h>
#include <DBCatalogue.h>
#include <DBEvent.h>
#include <DBTag.h>

struct CatalogueInspectorWidget::CatalogueInspectorWidgetPrivate {
    std::shared_ptr<DBCatalogue> m_DisplayedCatalogue = nullptr;
    std::shared_ptr<DBEvent> m_DisplayedEvent = nullptr;

    void connectCatalogueUpdateSignals(CatalogueInspectorWidget *inspector,
                                       Ui::CatalogueInspectorWidget *ui);
    void connectEventUpdateSignals(CatalogueInspectorWidget *inspector,
                                   Ui::CatalogueInspectorWidget *ui);
};

CatalogueInspectorWidget::CatalogueInspectorWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueInspectorWidget),
          impl{spimpl::make_unique_impl<CatalogueInspectorWidgetPrivate>()}
{
    ui->setupUi(this);
    showPage(Page::Empty);

    impl->connectCatalogueUpdateSignals(this, ui);
    impl->connectEventUpdateSignals(this, ui);
}

CatalogueInspectorWidget::~CatalogueInspectorWidget()
{
    delete ui;
}

void CatalogueInspectorWidget::CatalogueInspectorWidgetPrivate::connectCatalogueUpdateSignals(
    CatalogueInspectorWidget *inspector, Ui::CatalogueInspectorWidget *ui)
{
    connect(ui->leCatalogueName, &QLineEdit::editingFinished, [ui, inspector, this]() {
        if (ui->leCatalogueName->text() != m_DisplayedCatalogue->getName()) {
            m_DisplayedCatalogue->setName(ui->leCatalogueName->text());
            emit inspector->catalogueUpdated(m_DisplayedCatalogue);
        }
    });

    connect(ui->leCatalogueAuthor, &QLineEdit::editingFinished, [ui, inspector, this]() {
        if (ui->leCatalogueAuthor->text() != m_DisplayedCatalogue->getAuthor()) {
            m_DisplayedCatalogue->setAuthor(ui->leCatalogueAuthor->text());
            emit inspector->catalogueUpdated(m_DisplayedCatalogue);
        }
    });
}

void CatalogueInspectorWidget::CatalogueInspectorWidgetPrivate::connectEventUpdateSignals(
    CatalogueInspectorWidget *inspector, Ui::CatalogueInspectorWidget *ui)
{
    connect(ui->leEventName, &QLineEdit::editingFinished, [ui, inspector, this]() {
        if (ui->leEventName->text() != m_DisplayedEvent->getName()) {
            m_DisplayedEvent->setName(ui->leEventName->text());
            emit inspector->eventUpdated(m_DisplayedEvent);
        }
    });

    connect(ui->leEventMission, &QLineEdit::editingFinished, [ui, inspector, this]() {
        //        if (ui->leEventMission->text() != m_DisplayedEvent->getMission()) {
        //            m_DisplayedEvent->setMission(ui->leEventMission->text());
        //            emit inspector->eventUpdated(m_DisplayedEvent);
        //        }
    });

    connect(ui->leEventProduct, &QLineEdit::editingFinished, [ui, inspector, this]() {
        //        if (ui->leEventProduct->text() != m_DisplayedEvent->getProduct()) {
        //            m_DisplayedEvent->setProduct(ui->leEventProduct->text());
        //            emit inspector->eventUpdated(m_DisplayedEvent);
        //        }
    });

    connect(ui->leEventTags, &QLineEdit::editingFinished, [ui, inspector, this]() {
        // TODO
    });

    connect(ui->dateTimeEventTStart, &QDateTimeEdit::editingFinished, [ui, inspector, this]() {
        //        auto time = DateUtils::secondsSinceEpoch(ui->dateTimeEventTStart->dateTime());
        //        if (time != m_DisplayedEvent->getTStart()) {
        //            m_DisplayedEvent->setTStart(time);
        //            emit inspector->eventUpdated(m_DisplayedEvent);
        //        }
    });

    connect(ui->dateTimeEventTEnd, &QDateTimeEdit::editingFinished, [ui, inspector, this]() {
        //        auto time = DateUtils::secondsSinceEpoch(ui->dateTimeEventTEnd->dateTime());
        //        if (time != m_DisplayedEvent->getTEnd()) {
        //            m_DisplayedEvent->setTEnd(time);
        //            emit inspector->eventUpdated(m_DisplayedEvent);
        //        }
    });
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
    //    ui->leEventMission->setText(event->getMission());
    //    ui->leEventProduct->setText(event->getProduct());

    QString tagList;
    auto tags = event->getTags();
    for (auto tag : tags) {
        tagList += tag.getName();
        tagList += ' ';
    }

    ui->leEventTags->setText(tagList);

    //    ui->dateTimeEventTStart->setDateTime(DateUtils::dateTime(event->getTStart()));
    //    ui->dateTimeEventTEnd->setDateTime(DateUtils::dateTime(event->getTEnd()));

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
