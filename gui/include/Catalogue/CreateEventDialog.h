#ifndef SCIQLOP_CREATEEVENTDIALOG_H
#define SCIQLOP_CREATEEVENTDIALOG_H

#include <Common/spimpl.h>
#include <QDialog>
#include <memory>

namespace Ui {
class CreateEventDialog;
}

class DBCatalogue;

class CreateEventDialog : public QDialog {
    Q_OBJECT

public:
    explicit CreateEventDialog(QWidget *parent = 0);
    virtual ~CreateEventDialog();

    void hideCatalogueChoice();

    QString eventName() const;

    std::shared_ptr<DBCatalogue> selectedCatalogue() const;
    QString catalogueName() const;

private:
    Ui::CreateEventDialog *ui;

    class CreateEventDialogPrivate;
    spimpl::unique_impl_ptr<CreateEventDialogPrivate> impl;
};

#endif // SCIQLOP_CREATEEVENTDIALOG_H
