#include <Catalogue2/eventsmodel.h>
#include <Catalogue2/eventstreeview.h>

EventsTreeView::EventsTreeView(QWidget* parent) : QTreeView(parent)
{
    this->setModel(new EventsModel());
}

void EventsTreeView::setEvents(std::vector<CatalogueController::Event_ptr> events)
{
    static_cast<EventsModel*>(this->model())->setEvents(events);
}
