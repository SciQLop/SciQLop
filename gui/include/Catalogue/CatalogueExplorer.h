#ifndef SCIQLOP_CATALOGUEEXPLORER_H
#define SCIQLOP_CATALOGUEEXPLORER_H

#include <QDialog>

namespace Ui {
class CatalogueExplorer;
}

class CatalogueExplorer : public QDialog {
    Q_OBJECT

public:
    explicit CatalogueExplorer(QWidget *parent = 0);
    virtual ~CatalogueExplorer();

private:
    Ui::CatalogueExplorer *ui;
};

#endif // SCIQLOP_CATALOGUEEXPLORER_H
