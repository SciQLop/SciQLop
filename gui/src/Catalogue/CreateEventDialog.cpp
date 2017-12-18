#include "Catalogue/CreateEventDialog.h"
#include "ui_CreateEventDialog.h"

#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>

#include <DBCatalogue.h>

struct CreateEventDialog::CreateEventDialogPrivate {
    QVector<std::shared_ptr<DBCatalogue> > m_DisplayedCatalogues;
};

CreateEventDialog::CreateEventDialog(QWidget *parent)
        : QDialog(parent),
          ui(new Ui::CreateEventDialog),
          impl{spimpl::make_unique_impl<CreateEventDialogPrivate>()}
{
    ui->setupUi(this);

    connect(ui->buttonBox, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(ui->buttonBox, &QDialogButtonBox::rejected, this, &QDialog::reject);

    auto catalogues = sqpApp->catalogueController().retrieveCatalogues();
    for (auto cat : catalogues) {
        ui->cbCatalogue->addItem(cat->getName());
        impl->m_DisplayedCatalogues << cat;
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
