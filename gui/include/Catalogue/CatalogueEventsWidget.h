#ifndef SCIQLOP_CATALOGUEEVENTSWIDGET_H
#define SCIQLOP_CATALOGUEEVENTSWIDGET_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QWidget>

class DBCatalogue;
class DBEvent;
class DBEventProduct;
class VisualizationWidget;
class VisualizationSelectionZoneItem;

namespace Ui {
class CatalogueEventsWidget;
}

Q_DECLARE_LOGGING_CATEGORY(LOG_CatalogueEventsWidget)

class CatalogueEventsWidget : public QWidget {
    Q_OBJECT

signals:
    void eventsSelected(const QVector<std::shared_ptr<DBEvent> > &event);
    void eventsRemoved(const QVector<std::shared_ptr<DBEvent> > &event);
    void eventProductsSelected(
        const QVector<QPair<std::shared_ptr<DBEvent>, std::shared_ptr<DBEventProduct> > >
            &eventproducts);
    void selectionCleared();
    void selectionZoneAdded(const std::shared_ptr<DBEvent> &event, const QString &productId,
                            VisualizationSelectionZoneItem *selectionZone);

    void eventCataloguesModified(const QVector<std::shared_ptr<DBCatalogue> > &catalogues);

public:
    explicit CatalogueEventsWidget(QWidget *parent = 0);
    virtual ~CatalogueEventsWidget();

    void setVisualizationWidget(VisualizationWidget *visualization);

    void addEvent(const std::shared_ptr<DBEvent> &event);
    void setEventChanges(const std::shared_ptr<DBEvent> &event, bool hasChanges);

    QVector<std::shared_ptr<DBCatalogue> > displayedCatalogues() const;
    bool isAllEventsDisplayed() const;
    bool isEventDisplayed(const std::shared_ptr<DBEvent> &event) const;

    void refreshEvent(const std::shared_ptr<DBEvent> &event);

public slots:
    void populateWithCatalogues(const QVector<std::shared_ptr<DBCatalogue> > &catalogues);
    void populateWithAllEvents();
    void clear();
    void refresh();

private:
    Ui::CatalogueEventsWidget *ui;

    class CatalogueEventsWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueEventsWidgetPrivate> impl;

private slots:
    void emitSelection();
};

#endif // SCIQLOP_CATALOGUEEVENTSWIDGET_H
