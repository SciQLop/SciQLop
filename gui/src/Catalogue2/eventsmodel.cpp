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
#include <SqpApplication.h>

EventsModel::EventsModel(QObject* parent) : QAbstractItemModel(parent) {}

EventsModel::ItemType EventsModel::type(const QModelIndex& index) const
{
    if (!index.isValid())
    {
        return ItemType::None;
    }
    else if (index.internalPointer() == nullptr)
    {
        return ItemType::Event;
    }
    else
    {
        return ItemType::Product;
    }
}

QVariant EventsModel::data(int col, const CatalogueController::Event_ptr& event) const
{
    switch (static_cast<Columns>(col))
    {
        case EventsModel::Columns::Name:
            return QString::fromStdString(event->name);
        case EventsModel::Columns::TStart:
            if (auto start = event->startTime())
                return DateUtils::dateTime(*start).toString(DATETIME_FORMAT_ONE_LINE);
            else
                return QVariant {};
        case EventsModel::Columns::TEnd:
            if (auto stop = event->stopTime())
                return DateUtils::dateTime(*stop).toString(DATETIME_FORMAT_ONE_LINE);
            else
                return QVariant {};
        case EventsModel::Columns::Product:
        {
            QStringList eventProductList;
            for (const auto& evtProduct : event->products)
            {
                eventProductList << QString::fromStdString(evtProduct.name);
            }
            return eventProductList.join(";");
        }
        case EventsModel::Columns::Tags:
        {
            QString tagList;
            for (const auto& tag : event->tags)
            {
                tagList += QString::fromStdString(tag);
                tagList += ' ';
            }
            return tagList;
        }
        default:
            break;
    }
    return QVariant {};
}

QVariant EventsModel::data(int col, const CatalogueController::Product_t& product) const
{
    switch (static_cast<Columns>(col))
    {
        case EventsModel::Columns::Name:
            return QString::fromStdString(product.name);
        case EventsModel::Columns::TStart:
            return DateUtils::dateTime(product.startTime).toString(DATETIME_FORMAT_ONE_LINE);
        case EventsModel::Columns::TEnd:
            return DateUtils::dateTime(product.stopTime).toString(DATETIME_FORMAT_ONE_LINE);
        case EventsModel::Columns::Product:
            return QString::fromStdString(product.name);
        default:
            break;
    }
    return QVariant {};
}

QVariant EventsModel::data(const QModelIndex& index, int role) const
{
    if (_events.size() && index.isValid() && role == Qt::DisplayRole)
    {
        switch (type(index))
        {
            case EventsModel::ItemType::Event:
                return data(index.column(), _events[index.row()]);
            case EventsModel::ItemType::Product:
            {
                auto event = static_cast<CatalogueController::Event_t*>(index.internalPointer());
                return data(index.column(), event->products[index.row()]);
            }
            default:
                break;
        }
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
        case EventsModel::ItemType::None:
            return createIndex(row, column, nullptr);
        case EventsModel::ItemType::Event:
        {
            return createIndex(row, column, _events[parent.row()].get());
        }
        case EventsModel::ItemType::Product:
            break;
        default:
            break;
    }

    return QModelIndex();
}

QModelIndex EventsModel::parent(const QModelIndex& index) const
{
    switch (type(index))
    {
        case EventsModel::ItemType::None:
            break;
        case EventsModel::ItemType::Event:
            break;
        case EventsModel::ItemType::Product:
        {
            auto parentEvent = static_cast<CatalogueController::Event_t*>(index.internalPointer());
            auto pos = std::distance(std::cbegin(_events),
                std::find_if(std::cbegin(_events), std::cend(_events),
                    [parentEvent](auto event) { return event.get() == parentEvent; }));
            if (pos >= 0 && pos < _events.size())
            {
                return createIndex(pos, 0);
            }
        }
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
        case EventsModel::ItemType::None:
            return _events.size();
        case EventsModel::ItemType::Event:
            return _events[parent.row()]->products.size();
            break;
        case EventsModel::ItemType::Product:
            break;
        default:
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

void EventsModel::sort(int column, Qt::SortOrder order) {}
