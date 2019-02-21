#ifndef EVENTSTREEVIEW_H
#define EVENTSTREEVIEW_H

#include <Catalogue/CatalogueController.h>
#include <QObject>
#include <QTreeView>

class EventsTreeView : public QTreeView
{
    Q_OBJECT
public:
    EventsTreeView(QWidget* parent = nullptr);

public slots:
    void setEvents(std::vector<CatalogueController::Event_ptr> events);
};

#endif // EVENTSTREEVIEW_H
