#ifndef CATALOGUEEVENTSWIDGET_H
#define CATALOGUEEVENTSWIDGET_H

#include <QWidget>

namespace Ui {
class CatalogueEventsWidget;
}

class CatalogueEventsWidget : public QWidget {
    Q_OBJECT

public:
    explicit CatalogueEventsWidget(QWidget *parent = 0);
    ~CatalogueEventsWidget();

private:
    Ui::CatalogueEventsWidget *ui;
};

#endif // CATALOGUEEVENTSWIDGET_H
