#ifndef SCIQLOP_CATALOGUEEXPLORER_H
#define SCIQLOP_CATALOGUEEXPLORER_H

#include <Common/spimpl.h>
#include <QDialog>

namespace Ui {
class CatalogueExplorer;
}

class VisualizationWidget;

class CatalogueExplorer : public QDialog {
    Q_OBJECT

public:
    explicit CatalogueExplorer(QWidget *parent = 0);
    virtual ~CatalogueExplorer();

    void setVisualizationWidget(VisualizationWidget *visualization);

private:
    Ui::CatalogueExplorer *ui;

    class CatalogueExplorerPrivate;
    spimpl::unique_impl_ptr<CatalogueExplorerPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEXPLORER_H
