#include "Catalogue/CatalogueEventsModel.h"

#include <Catalogue/CatalogueController.h>
#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>
#include <Data/DateTimeRange.h>
#include <Repository.hpp>
#include <SqpApplication.h>
#include <Time/TimeController.h>

#include <list>
#include <unordered_map>

#include <QHash>
#include <QMimeData>

Q_LOGGING_CATEGORY(LOG_CatalogueEventsModel, "CatalogueEventsModel")

const auto EVENT_ITEM_TYPE = 1;
const auto EVENT_PRODUCT_ITEM_TYPE = 2;

struct CatalogueEventsModel::CatalogueEventsModelPrivate
{
    std::vector<CatalogueController::Event_ptr> m_Events;
    // std::unordered_map<DBEvent*, QVector<std::shared_ptr<DBEventProduct>>> m_EventProducts;
    // QVector<std::shared_ptr<DBCatalogue>> m_SourceCatalogue;

    QStringList columnNames()
    {
        return QStringList { tr("Event"), tr("TStart"), tr("TEnd"), tr("Tags"), tr("Product"),
            tr("") };
    }

    QVariant sortData(int col, const CatalogueController::Event_ptr& event) const
    {
        if (col == (int)CatalogueEventsModel::Column::Validation)
        {
            auto hasChanges = sqpApp->catalogueController().hasUnsavedChanges(event);
            return hasChanges ? true : QVariant();
        }

        return eventData(col, event);
    }

    QVariant eventData(int col, const CatalogueController::Event_ptr& event) const
    {
        switch (static_cast<Column>(col))
        {
            case CatalogueEventsModel::Column::Name:
                return QString::fromStdString(event->name);
            case CatalogueEventsModel::Column::TStart:
                if (auto start = event->startTime())
                    return DateUtils::dateTime(*start).toString(DATETIME_FORMAT_ONE_LINE);
                else
                    return QVariant {};
            case CatalogueEventsModel::Column::TEnd:
                if (auto stop = event->stopTime())
                    return DateUtils::dateTime(*stop).toString(DATETIME_FORMAT_ONE_LINE);
                else
                    return QVariant {};
            case CatalogueEventsModel::Column::Product:
            {
                QStringList eventProductList;
                for (const auto& evtProduct : event->products)
                {
                    eventProductList << QString::fromStdString(evtProduct.name);
                }
                return eventProductList.join(";");
            }
            case CatalogueEventsModel::Column::Tags:
            {
                QString tagList;
                for (const auto& tag : event->tags)
                {
                    tagList += QString::fromStdString(tag);
                    tagList += ' ';
                }
                return tagList;
            }
            case CatalogueEventsModel::Column::Validation:
                return QVariant();
            default:
                break;
        }

        Q_ASSERT(false);
        return QStringLiteral("Unknown Data");
    }

    void parseEventProduct(const CatalogueController::Event_ptr& event)
    {
        //        for (auto& product : event->products)
        //        {
        //            m_EventProducts[event.get()].append(std::make_shared<DBEventProduct>(product));
        //        }
    }

    std::size_t nbEventProducts(const CatalogueController::Event_ptr& event) const
    {
        if (event)
        {
            return event->products.size();
        }
        else
        {
            return 0;
        }
    }

    QVariant eventProductData(int col, const CatalogueController::Product_t& eventProduct) const
    {
        switch (static_cast<Column>(col))
        {
            case CatalogueEventsModel::Column::Name:
                return QString::fromStdString(eventProduct.name);
            case CatalogueEventsModel::Column::TStart:
                return DateUtils::dateTime(eventProduct.startTime)
                    .toString(DATETIME_FORMAT_ONE_LINE);
            case CatalogueEventsModel::Column::TEnd:
                return DateUtils::dateTime(eventProduct.stopTime)
                    .toString(DATETIME_FORMAT_ONE_LINE);
            case CatalogueEventsModel::Column::Product:
                return QString::fromStdString(eventProduct.name);
            case CatalogueEventsModel::Column::Tags:
                return QString();
            case CatalogueEventsModel::Column::Validation:
                return QVariant();
            default:
                break;
        }

        Q_ASSERT(false);
        return QStringLiteral("Unknown Data");
    }

    void refreshChildrenOfIndex(CatalogueEventsModel* model, const QModelIndex& index) const
    {
        auto childCount = model->rowCount(index);
        auto colCount = model->columnCount();
        emit model->dataChanged(
            model->index(0, 0, index), model->index(childCount, colCount, index));
    }
};

CatalogueEventsModel::CatalogueEventsModel(QObject* parent)
        : QAbstractItemModel(parent)
        , impl { spimpl::make_unique_impl<CatalogueEventsModelPrivate>() }
{
}

void CatalogueEventsModel::setSourceCatalogues(
    const QVector<std::shared_ptr<DBCatalogue>>& catalogues)
{
    // impl->m_SourceCatalogue = catalogues;
}

void CatalogueEventsModel::setEvents(const std::vector<CatalogueController::Event_ptr>& events)
{
    beginResetModel();

    impl->m_Events = events;

    endResetModel();
}

CatalogueController::Event_ptr CatalogueEventsModel::getEvent(const QModelIndex& index) const
{
    if (itemTypeOf(index) == CatalogueEventsModel::ItemType::Event)
    {
        return impl->m_Events[index.row()];
    }
    else
    {
        return nullptr;
    }
}

CatalogueController::Event_ptr CatalogueEventsModel::getParentEvent(const QModelIndex& index) const
{
    if (itemTypeOf(index) == CatalogueEventsModel::ItemType::EventProduct)
    {
        return getEvent(index.parent());
    }
    else
    {
        return nullptr;
    }
}

std::optional<CatalogueController::Product_t> CatalogueEventsModel::getEventProduct(
    const QModelIndex& index) const
{
    if (itemTypeOf(index) == CatalogueEventsModel::ItemType::EventProduct)
    {
        auto event = *static_cast<CatalogueController::Event_ptr*>(index.internalPointer());
        return event->products[index.row()];
    }
    else
    {
        return std::nullopt;
    }
}

void CatalogueEventsModel::addEvent(const std::shared_ptr<DBEvent>& event)
{
    //    beginInsertRows(QModelIndex(), impl->m_Events.count(), impl->m_Events.count());
    //    impl->m_Events.append(event);
    //    impl->parseEventProduct(event);
    //    endInsertRows();

    //    // Also refreshes its children event products
    //    auto eventIndex = index(impl->m_Events.count(), 0);
    //    impl->refreshChildrenOfIndex(this, eventIndex);
}

void CatalogueEventsModel::removeEvent(const std::shared_ptr<DBEvent>& event)
{
    //    auto index = impl->m_Events.indexOf(event);
    //    if (index >= 0)
    //    {
    //        beginRemoveRows(QModelIndex(), index, index);
    //        impl->m_Events.removeAt(index);
    //        impl->m_EventProducts.erase(event.get());
    //        endRemoveRows();
    //    }
}

std::vector<CatalogueController::Event_ptr> CatalogueEventsModel::events() const
{
    return impl->m_Events;
}

void CatalogueEventsModel::refreshEvent(
    const CatalogueController::Event_ptr& event, bool refreshEventProducts)
{
    auto eventIndex = indexOf(event);
    if (eventIndex.isValid())
    {
        // Refreshes the event line
        auto colCount = columnCount();
        emit dataChanged(eventIndex, index(eventIndex.row(), colCount));
        // Also refreshes its children event products
        impl->refreshChildrenOfIndex(this, eventIndex);
    }
    else
    {
        qCWarning(LOG_CatalogueEventsModel()) << "refreshEvent: event not found.";
    }
}

QModelIndex CatalogueEventsModel::indexOf(const CatalogueController::Event_ptr& event) const
{
    auto pos = std::distance(std::begin(impl->m_Events),
        find(std::begin(impl->m_Events), std::end(impl->m_Events), event));
    if (pos >= 0 && pos < impl->m_Events.size())
    {
        return index(pos, 0);
    }

    return QModelIndex();
}

QModelIndex CatalogueEventsModel::index(int row, int column, const QModelIndex& parent) const
{
    if (!hasIndex(row, column, parent))
    {
        return QModelIndex();
    }

    switch (itemTypeOf(parent))
    {
        case CatalogueEventsModel::ItemType::Root:
            return createIndex(row, column);
        case CatalogueEventsModel::ItemType::Event:
        {
            auto event = getEvent(parent);
            return createIndex(row, column, event.get());
        }
        case CatalogueEventsModel::ItemType::EventProduct:
            break;
        default:
            break;
    }

    return QModelIndex();
}

QModelIndex CatalogueEventsModel::parent(const QModelIndex& index) const
{
    switch (itemTypeOf(index))
    {
        case CatalogueEventsModel::ItemType::EventProduct:
        {
            auto parentEvent
                = *static_cast<CatalogueController::Event_ptr*>(index.internalPointer());
            auto it = std::find_if(impl->m_Events.cbegin(), impl->m_Events.cend(),
                [parentEvent](auto event) { return event.get() == parentEvent.get(); });

            if (it != impl->m_Events.cend())
            {
                return createIndex(it - impl->m_Events.cbegin(), 0);
            }
            else
            {
                return QModelIndex();
            }
        }
        case CatalogueEventsModel::ItemType::Root:
            break;
        case CatalogueEventsModel::ItemType::Event:
            break;
        default:
            break;
    }

    return QModelIndex();
}

int CatalogueEventsModel::rowCount(const QModelIndex& parent) const
{
    if (parent.column() > 0)
    {
        return 0;
    }

    switch (itemTypeOf(parent))
    {
        case CatalogueEventsModel::ItemType::Root:
            return impl->m_Events.size();
        case CatalogueEventsModel::ItemType::Event:
        {
            auto event = getEvent(parent);
            return event->products.size();
        }
        case CatalogueEventsModel::ItemType::EventProduct:
            break;
        default:
            break;
    }

    return 0;
}

int CatalogueEventsModel::columnCount(const QModelIndex& parent) const
{
    return static_cast<int>(CatalogueEventsModel::Column::NbColumn);
}

Qt::ItemFlags CatalogueEventsModel::flags(const QModelIndex& index) const
{
    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
}

QVariant CatalogueEventsModel::data(const QModelIndex& index, int role) const
{
    if (index.isValid())
    {

        auto type = itemTypeOf(index);
        if (type == CatalogueEventsModel::ItemType::Event)
        {
            auto event = getEvent(index);
            switch (role)
            {
                case Qt::DisplayRole:
                    return impl->eventData(index.column(), event);
                    break;
            }
        }
        else if (type == CatalogueEventsModel::ItemType::EventProduct)
        {
            auto product = getEventProduct(index);
            if (product)
            {
                switch (role)
                {
                    case Qt::DisplayRole:
                        return impl->eventProductData(index.column(), *product);
                        break;
                }
            }
        }
    }

    return QVariant {};
}

QVariant CatalogueEventsModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole)
    {
        return impl->columnNames().value(section);
    }

    return QVariant();
}

void CatalogueEventsModel::sort(int column, Qt::SortOrder order)
{
    beginResetModel();
    std::sort(
        impl->m_Events.begin(), impl->m_Events.end(), [this, column, order](auto e1, auto e2) {
            auto data1 = impl->sortData(column, e1);
            auto data2 = impl->sortData(column, e2);

            auto result = data1.toString() < data2.toString();

            return order == Qt::AscendingOrder ? result : !result;
        });

    endResetModel();
    emit modelSorted();
}

Qt::DropActions CatalogueEventsModel::supportedDragActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

QStringList CatalogueEventsModel::mimeTypes() const
{
    return { MIME_TYPE_EVENT_LIST, MIME_TYPE_SOURCE_CATALOGUE_LIST, MIME_TYPE_TIME_RANGE };
}

QMimeData* CatalogueEventsModel::mimeData(const QModelIndexList& indexes) const
{
    auto mimeData = new QMimeData;

    //    bool isFirst = true;

    //    QVector<std::shared_ptr<DBEvent>> eventList;
    //    QVector<std::shared_ptr<DBEventProduct>> eventProductList;

    //    DateTimeRange firstTimeRange;
    //    for (const auto& index : indexes)
    //    {
    //        if (index.column() == 0)
    //        { // only the first column

    //            auto type = itemTypeOf(index);
    //            if (type == ItemType::Event)
    //            {
    //                auto event = getEvent(index);
    //                eventList << event;

    //                if (isFirst)
    //                {
    //                    isFirst = false;
    //                    firstTimeRange.m_TStart = event->;
    //                    firstTimeRange.m_TEnd = event->getTEnd();
    //                }
    //            }
    //            else if (type == ItemType::EventProduct)
    //            {
    //                auto product = getEventProduct(index);
    //                eventProductList << product;

    //                if (isFirst)
    //                {
    //                    isFirst = false;
    //                    firstTimeRange.m_TStart = product->getTStart();
    //                    firstTimeRange.m_TEnd = product->getTEnd();
    //                }
    //            }
    //        }
    //    }

    //    if (!eventList.isEmpty() && eventProductList.isEmpty())
    //    {
    //        auto eventsEncodedData = sqpApp->catalogueController().mimeDataForEvents(eventList);
    //        mimeData->setData(MIME_TYPE_EVENT_LIST, eventsEncodedData);

    //        auto sourceCataloguesEncodedData
    //            = sqpApp->catalogueController().mimeDataForCatalogues(impl->m_SourceCatalogue);
    //        mimeData->setData(MIME_TYPE_SOURCE_CATALOGUE_LIST, sourceCataloguesEncodedData);
    //    }

    //    if (eventList.count() + eventProductList.count() == 1)
    //    {
    //        // No time range MIME data if multiple events are dragged
    //        auto timeEncodedData = TimeController::mimeDataForTimeRange(firstTimeRange);
    //        mimeData->setData(MIME_TYPE_TIME_RANGE, timeEncodedData);
    //    }

    return mimeData;
}

CatalogueEventsModel::ItemType CatalogueEventsModel::itemTypeOf(const QModelIndex& index) const
{
    if (!index.isValid())
    {
        return ItemType::Root;
    }
    else if (index.internalPointer() == nullptr)
    {
        return ItemType::Event;
    }
    else
    {
        return ItemType::EventProduct;
    }
}
