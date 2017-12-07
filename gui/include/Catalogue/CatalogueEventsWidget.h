#ifndef SCIQLOP_CATALOGUEEVENTSWIDGET_H
#define SCIQLOP_CATALOGUEEVENTSWIDGET_H

#include <Common/spimpl.h>
#include <QWidget>

namespace Ui {
class CatalogueEventsWidget;
}

class CatalogueEventsWidget : public QWidget {
    Q_OBJECT

signals:
    void eventSelected(const QString &event);

public:
    explicit CatalogueEventsWidget(QWidget *parent = 0);
    virtual ~CatalogueEventsWidget();

public slots:
    void populateWithCatalogue(const QString &catalogue);

private:
    Ui::CatalogueEventsWidget *ui;

    class CatalogueEventsWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsWidgetPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEVENTSWIDGET_H
