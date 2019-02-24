/*
    This file is part of SciQLop.

    SciQLop is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    SciQLop is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with SciQLop.  If not, see <https://www.gnu.org/licenses/>.
*/
#include <Catalogue2/eventsmodel.h>
#include <Catalogue2/eventstreeview.h>

EventsTreeView::EventsTreeView(QWidget* parent) : QTreeView(parent)
{
    this->setModel(new EventsModel());
    connect(this->selectionModel(), &QItemSelectionModel::currentChanged, [this](const QModelIndex &current, const QModelIndex &previous){
        Q_UNUSED(previous);
        this->_itemSelected(current);
    });
}

void EventsTreeView::setEvents(std::vector<CatalogueController::Event_ptr> events)
{
    static_cast<EventsModel*>(this->model())->setEvents(events);
}

void EventsTreeView::_itemSelected(const QModelIndex &index)
{
    auto item = EventsModel::to_item(index);
    if (item->type == EventsModel::ItemType::Event)
    {
        emit eventSelected(item->event());
    }
    else if (item->type == EventsModel::ItemType::Product)
    {
        emit productSelected(item->product(), item->parent->event());
    }
}
