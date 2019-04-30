#ifndef BROWSER_H
#define BROWSER_H

#include <Catalogue/CatalogueController.h>
#include <QWidget>

namespace Ui
{
class Browser;
}

class CataloguesBrowser : public QWidget
{
    Q_OBJECT

public:
    explicit CataloguesBrowser(QWidget* parent = nullptr);
    ~CataloguesBrowser();
private slots:
    void repositorySelected(const QString& repo);
    void catalogueSelected(const CatalogueController::Catalogue_ptr& catalogue);
    void eventSelected(const CatalogueController::Event_ptr& event);
    void productSelected(
        const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event);

private:
    Ui::Browser* ui;
};

#endif // BROWSER_H
