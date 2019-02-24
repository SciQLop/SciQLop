#ifndef BROWSER_H
#define BROWSER_H

#include <QWidget>
#include <Catalogue/CatalogueController.h>

namespace Ui {
class Browser;
}

class Browser : public QWidget
{
    Q_OBJECT

public:
    explicit Browser(QWidget *parent = nullptr);
    ~Browser();
private slots:
    void repositorySelected(const QString& repo);
    void catalogueSelected(const CatalogueController::Catalogue_ptr& catalogue);
    void eventSelected(const CatalogueController::Event_ptr& event);
    void productSelected(const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event);
private:
    Ui::Browser *ui;
};

#endif // BROWSER_H
