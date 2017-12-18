#ifndef SCIQLOP_CATALOGUEEVENTSWIDGET_H
#define SCIQLOP_CATALOGUEEVENTSWIDGET_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QWidget>

class DBCatalogue;
class DBEvent;
class DBEventProduct;
class VisualizationWidget;

namespace Ui {
class CatalogueEventsWidget;
}

Q_DECLARE_LOGGING_CATEGORY(LOG_CatalogueEventsWidget)

class CatalogueEventsWidget : public QWidget {
    Q_OBJECT

signals:
    void eventsSelected(const QVector<std::shared_ptr<DBEvent> > &event);
    void eventProductsSelected(
        const QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > >
            &eventproducts);
    void selectionCleared();

public:
    explicit CatalogueEventsWidget(QWidget *parent = 0);
    virtual ~CatalogueEventsWidget();

    void setVisualizationWidget(VisualizationWidget *visualization);

    void setEventChanges(const std::shared_ptr<DBEvent> &event, bool hasChanges);

public slots:
    void populateWithCatalogues(const QVector<std::shared_ptr<DBCatalogue> > &catalogues);
    void populateWithAllEvents();

private:
    Ui::CatalogueEventsWidget *ui;

    class CatalogueEventsWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsWidgetPrivate> impl;
};

#endif // SCIQLOP_CATALOGUEEVENTSWIDGET_H
