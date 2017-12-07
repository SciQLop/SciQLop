#ifndef SCIQLOP_CATALOGUEEVENTSWIDGET_H
#define SCIQLOP_CATALOGUEEVENTSWIDGET_H

#include <Common/spimpl.h>
#include <QWidget>

namespace Ui {
class CatalogueEventsWidget;
}

class CatalogueEventsWidget : public QWidget {
    Q_OBJECT

public:
    explicit CatalogueEventsWidget(QWidget *parent = 0);
    virtual ~CatalogueEventsWidget();

private:
    Ui::CatalogueEventsWidget *ui;

    class CatalogueEventsWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsWidgetPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEVENTSWIDGET_H
