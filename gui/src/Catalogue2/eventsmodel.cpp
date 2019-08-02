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
#include "Catalogue2/eventsmodel.h"
#include <Common/containers.h>
#include <SqpApplication.h>

EventsModel::EventsModel(QObject* parent) : QAbstractItemModel(parent) {}

EventsModel::ItemType EventsModel::type(const QModelIndex& index) const
{
    if (EventsModelItem* item = to_item(index))
    {
        return item->type;
    }
    return ItemType::None;
}

QVariant EventsModel::data(const QModelIndex& index, int role) const
{
    if (index.isValid())
    {
        return to_item(index)->data(index.column(), role);
    }
    return QVariant {};
}

QModelIndex EventsModel::index(int row, int column, const QModelIndex& parent) const
{
    if (!hasIndex(row, column, parent))
    {
        return QModelIndex();
    }

    switch (type(parent))
    {
        case ItemType::None: // is an event
            return createIndex(row, column, _items[row].get());
        case ItemType::Event: // is a product
            return createIndex(row, column, to_item(parent)->children[row].get());
        case ItemType::Product:
            QModelIndex();
    }

    return QModelIndex();
}

QModelIndex EventsModel::parent(const QModelIndex& index) const
{
    auto item = to_item(index);
    if (item->type == ItemType::Product)
    {
        auto repoIndex = SciQLop::containers::index_of(_items, item->parent);
        return createIndex(repoIndex, 0, item->parent);
    }
    return QModelIndex();
}

int EventsModel::rowCount(const QModelIndex& parent) const
{
    if (parent.column() > 0)
    {
        return 0;
    }
    switch (type(parent))
    {
        case ItemType::None:
            return _items.size();
        case ItemType::Event:
            return to_item(parent)->children.size();
        case ItemType::Product:
            break;
    }
    return 0;
}

int EventsModel::columnCount(const QModelIndex& parent) const
{
    return static_cast<int>(EventsModel::Columns::NbColumn);
}

QVariant EventsModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole && section < ColumnsNames.size())
    {
        return ColumnsNames[section];
    }

    return QVariant();
}

void EventsModel::sort(int column, Qt::SortOrder order)
{
    beginResetModel();
    switch (static_cast<Columns>(column))
    {
        case EventsModel::Columns::Name:
            std::sort(std::begin(_items), std::end(_items),
                [inverse = order != Qt::SortOrder::AscendingOrder](
                    const std::unique_ptr<EventsModelItem>& a,
                    const std::unique_ptr<EventsModelItem>& b) {
                    return (a->event()->name < b->event()->name) xor inverse;
                });
            break;
        case EventsModel::Columns::TStart:
            std::sort(std::begin(_items), std::end(_items),
                [inverse = order != Qt::SortOrder::AscendingOrder](
                    const std::unique_ptr<EventsModelItem>& a,
                    const std::unique_ptr<EventsModelItem>& b) {
                    if (auto t1 = a->event()->startTime(); auto t2 = b->event()->startTime())
                    {
                        if (t1 and t2)
                            return bool((t1.value() < t2.value()) xor inverse);
                    }
                    return true;
                });
            break;
        case EventsModel::Columns::TEnd:
            std::sort(std::begin(_items), std::end(_items),
                [inverse = order != Qt::SortOrder::AscendingOrder](
                    const std::unique_ptr<EventsModelItem>& a,
                    const std::unique_ptr<EventsModelItem>& b) {
                    if (auto t1 = a->event()->stopTime(); auto t2 = b->event()->stopTime())
                    {
                        if (t1 and t2)
                            return bool((t1.value() < t2.value()) xor inverse);
                    }
                    return true;
                });
            break;
        case EventsModel::Columns::Product:
            break;
        case EventsModel::Columns::Tags:
            break;
        default:
            break;
    }
    endResetModel();
}
