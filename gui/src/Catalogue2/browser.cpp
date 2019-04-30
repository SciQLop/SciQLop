#include "Catalogue2/browser.h"
#include "ui_browser.h"
#include <SqpApplication.h>

CataloguesBrowser::CataloguesBrowser(QWidget* parent)
        : QWidget(parent, Qt::Window), ui(new Ui::Browser)
{
    ui->setupUi(this);
    connect(ui->repositories, &RepositoriesTreeView::repositorySelected, this,
        &CataloguesBrowser::repositorySelected);
    connect(ui->repositories, &RepositoriesTreeView::catalogueSelected, this,
        &CataloguesBrowser::catalogueSelected);
    connect(ui->events, &EventsTreeView::eventSelected, this, &CataloguesBrowser::eventSelected);
    connect(
        ui->events, &EventsTreeView::productSelected, this, &CataloguesBrowser::productSelected);
}

CataloguesBrowser::~CataloguesBrowser()
{
    delete ui;
}

void CataloguesBrowser::repositorySelected(const QString& repo)
{
    this->ui->Infos->setCurrentIndex(0);
    this->ui->events->setEvents(sqpApp->catalogueController().events(repo));
    // TODO add a statistic API
    this->ui->catalogues_count->setText(
        QString::number(sqpApp->catalogueController().catalogues(repo).size()));
    this->ui->rep_events_count->setText(
        QString::number(sqpApp->catalogueController().events(repo).size()));
}

void CataloguesBrowser::catalogueSelected(const CatalogueController::Catalogue_ptr& catalogue)
{
    this->ui->Infos->setCurrentIndex(1);
    this->ui->events->setEvents(sqpApp->catalogueController().events(catalogue));
    this->ui->cat_events_count->setText(
        QString::number(sqpApp->catalogueController().events(catalogue).size()));
}

void CataloguesBrowser::eventSelected(const CatalogueController::Event_ptr& event)
{
    this->ui->Infos->setCurrentIndex(2);
    this->ui->Event->setEvent(event);
}

void CataloguesBrowser::productSelected(
    const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event)
{
    this->ui->Infos->setCurrentIndex(2);
    this->ui->Event->setProduct(product, event);
}
