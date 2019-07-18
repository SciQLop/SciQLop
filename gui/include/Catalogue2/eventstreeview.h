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
    ~EventsTreeView();

signals:
    void eventSelected(const CatalogueController::Event_ptr& event);
    void productSelected(
        const CatalogueController::Product_t& product, const CatalogueController::Event_ptr& event);

public slots:
    void setEvents(std::vector<CatalogueController::Event_ptr> events);

private:
    void _itemSelected(const QModelIndex& index);
};

#endif // EVENTSTREEVIEW_H
