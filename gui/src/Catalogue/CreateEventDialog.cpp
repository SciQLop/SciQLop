#include "Catalogue/CreateEventDialog.h"
#include "ui_CreateEventDialog.h"

#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>

#include <DBCatalogue.h>

struct CreateEventDialog::CreateEventDialogPrivate {
    QVector<std::shared_ptr<DBCatalogue> > m_DisplayedCatalogues;
};

CreateEventDialog::CreateEventDialog(const QVector<std::shared_ptr<DBCatalogue> > &catalogues,
                                     QWidget *parent)
        : QDialog(parent),
          ui(new Ui::CreateEventDialog),
          impl{spimpl::make_unique_impl<CreateEventDialogPrivate>()}
{
    ui->setupUi(this);

    connect(ui->buttonBox, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(ui->buttonBox, &QDialogButtonBox::rejected, this, &QDialog::reject);

    impl->m_DisplayedCatalogues = catalogues;
    for (auto cat : impl->m_DisplayedCatalogues) {
        ui->cbCatalogue->addItem(cat->getName());
    }
}

CreateEventDialog::~CreateEventDialog()
{
    delete ui;
}

void CreateEventDialog::hideCatalogueChoice()
{
    ui->cbCatalogue->hide();
    ui->lblCatalogue->hide();
}

QString CreateEventDialog::eventName() const
{
    return ui->leEvent->text();
}

std::shared_ptr<DBCatalogue> CreateEventDialog::selectedCatalogue() const
{
    auto catalogue = impl->m_DisplayedCatalogues.value(ui->cbCatalogue->currentIndex());
    if (!catalogue || catalogue->getName() != catalogueName()) {
        return nullptr;
    }

    return catalogue;
}

QString CreateEventDialog::catalogueName() const
{
    return ui->cbCatalogue->currentText();
}
