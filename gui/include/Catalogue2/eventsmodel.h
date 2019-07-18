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
#ifndef EVENTSMODEL_H
#define EVENTSMODEL_H
#include <Catalogue/CatalogueController.h>
#include <QAbstractItemModel>
#include <QIcon>
#include <array>

class EventsModel : public QAbstractItemModel
{
    Q_OBJECT

    enum class Columns
    {
        Name = 0,
        TStart = 1,
        TEnd = 2,
        Tags = 3,
        Product = 4,
        Validation = 5,
        NbColumn = 6
    };

    const std::array<QString, static_cast<int>(Columns::NbColumn)> ColumnsNames
        = { "Name", "Start time", "Stop time", "Tags", "Product(s)", "" };


public:
    enum class ItemType
    {
        None,
        Event,
        Product
    };

    struct EventsModelItem
    {
        ItemType type;
        std::variant<CatalogueController::Event_ptr, CatalogueController::Product_t> item;
        // EventsModelItem() : type { ItemType::None } {}
        EventsModelItem() = delete;
        EventsModelItem(const EventsModelItem&) = delete;
        EventsModelItem(EventsModelItem&&) = delete;
        EventsModelItem& operator=(const EventsModelItem&) = delete;
        EventsModelItem& operator=(EventsModelItem&&) = delete;
        EventsModelItem(const CatalogueController::Event_ptr& event)
                : type { ItemType::Event }, item { event }, parent { nullptr }, icon {}
        {
            std::transform(std::cbegin(event->products), std::cend(event->products),
                std::back_inserter(children),
                [this](auto& product) { return std::make_unique<EventsModelItem>(product, this); });
        }

        EventsModelItem(const CatalogueController::Product_t& product, EventsModelItem* parent)
                : type { ItemType::Product }, item { product }, parent { parent }, icon {}
        {
        }
        ~EventsModelItem() { children.clear(); }
        CatalogueController::Event_ptr event() const
        {
            return std::get<CatalogueController::Event_ptr>(item);
        }
        CatalogueController::Product_t product() const
        {
            return std::get<CatalogueController::Product_t>(item);
        }
        QVariant data(int col, int role) const
        {
            if (role == Qt::DisplayRole)
            {
                switch (type)
                {
                    case ItemType::Product:
                        return data(product(), col);
                    case ItemType::Event:
                        return data(event(), col);
                    default:
                        break;
                }
            }
            return QVariant {};
        }
        QVariant data(const CatalogueController::Event_ptr& event, int col) const
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

        QVariant data(const CatalogueController::Product_t& product, int col) const
        {
            switch (static_cast<Columns>(col))
            {
                case EventsModel::Columns::Name:
                    return QString::fromStdString(product.name);
                case EventsModel::Columns::TStart:
                    return DateUtils::dateTime(product.startTime)
                        .toString(DATETIME_FORMAT_ONE_LINE);
                case EventsModel::Columns::TEnd:
                    return DateUtils::dateTime(product.stopTime).toString(DATETIME_FORMAT_ONE_LINE);
                case EventsModel::Columns::Product:
                    return QString::fromStdString(product.name);
                default:
                    break;
            }
            return QVariant {};
        }

        QString text() const
        {
            if (type == ItemType::Event)
                return QString::fromStdString(event()->name);
            if (type == ItemType::Product)
                return QString::fromStdString(product().name);
            return QString();
        }
        std::vector<std::unique_ptr<EventsModelItem>> children;
        EventsModelItem* parent = nullptr;
        QIcon icon;
    };
    EventsModel(QObject* parent = nullptr);

    static inline EventsModelItem* to_item(const QModelIndex& index)
    {
        return static_cast<EventsModelItem*>(index.internalPointer());
    }

    ~EventsModel() { _items.clear(); }

    ItemType type(const QModelIndex& index) const;

    Qt::ItemFlags flags(const QModelIndex& index) const override
    {
        return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
    }
    QVariant data(const QModelIndex& index, int role = Qt::DisplayRole) const override;

    QModelIndex index(
        int row, int column, const QModelIndex& parent = QModelIndex()) const override;

    QModelIndex parent(const QModelIndex& index) const override;

    int rowCount(const QModelIndex& parent = QModelIndex()) const override;

    int columnCount(const QModelIndex& parent = QModelIndex()) const override;

    QVariant headerData(
        int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;

    void sort(int column, Qt::SortOrder order = Qt::AscendingOrder) override;

public slots:
    void setEvents(std::vector<CatalogueController::Event_ptr> events)
    {
        beginResetModel();
        _items.clear();
        std::transform(std::begin(events), std::end(events), std::back_inserter(_items),
            [](const auto& event) { return std::make_unique<EventsModelItem>(event); });
        endResetModel();
    }

private:
    std::vector<std::unique_ptr<EventsModelItem>> _items;
};

#endif // EVENTSMODEL_H
