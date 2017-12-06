#ifndef CATALOGUEINSPECTORWIDGET_H
#define CATALOGUEINSPECTORWIDGET_H

#include <QWidget>

namespace Ui {
class CatalogueInspectorWidget;
}

class CatalogueInspectorWidget : public QWidget {
    Q_OBJECT

public:
    explicit CatalogueInspectorWidget(QWidget *parent = 0);
    ~CatalogueInspectorWidget();

private:
    Ui::CatalogueInspectorWidget *ui;
};

#endif // CATALOGUEINSPECTORWIDGET_H
