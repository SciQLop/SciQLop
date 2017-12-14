#include "Catalogue/CatalogueEventsModel.h"

#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>
#include <DBEvent.h>
#include <DBEventProduct.h>
#include <DBTag.h>
#include <Data/SqpRange.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>

#include <list>
#include <unordered_map>

#include <QHash>
#include <QMimeData>

const auto EVENT_ITEM_TYPE = 1;
const auto EVENT_PRODUCT_ITEM_TYPE = 2;

struct CatalogueEventsModel::CatalogueEventsTableModelPrivate {
    QVector<std::shared_ptr<DBEvent> > m_Events;
    std::unordered_map<DBEvent *, QVector<std::shared_ptr<DBEventProduct> > > m_EventProducts;

    enum class Column { Name, TStart, TEnd, Tags, Product, NbColumn };
    QStringList columnNames()
    {
        return QStringList{tr("Event"), tr("TStart"), tr("TEnd"), tr("Tags"), tr("Product")};
    }

    QVariant eventData(int col, const std::shared_ptr<DBEvent> &event) const
    {
        switch (static_cast<Column>(col)) {
            case Column::Name:
                return event->getName();
            case Column::TStart:
                return "Oo"; // DateUtils::dateTime(event->getTStart());
            case Column::TEnd:
                return "oO"; // DateUtils::dateTime(event->getTEnd());
            case Column::Product: {
                auto eventProductsIt = m_EventProducts.find(event.get());
                if (eventProductsIt != m_EventProducts.cend()) {
                    return QString::number(m_EventProducts.at(event.get()).count()) + " product(s)";
                }
                else {
                    return "0 product";
                }
            }
            case Column::Tags: {
                QString tagList;
                auto tags = event->getTags();
                for (auto tag : tags) {
                    tagList += tag.getName();
                    tagList += ' ';
                }

                return tagList;
            }
            default:
                break;
        }

        Q_ASSERT(false);
        return QStringLiteral("Unknown Data");
    }

    void parseEventProduct(const std::shared_ptr<DBEvent> &event)
    {
        for (auto product : event->getEventProducts()) {
            m_EventProducts[event.get()].append(std::make_shared<DBEventProduct>(product));
        }
    }

    QVariant eventProductData(int col, const std::shared_ptr<DBEventProduct> &eventProduct) const
    {
        switch (static_cast<Column>(col)) {
            case Column::Name:
                return eventProduct->getProductId();
            case Column::TStart:
                return DateUtils::dateTime(eventProduct->getTStart());
            case Column::TEnd:
                return DateUtils::dateTime(eventProduct->getTEnd());
            case Column::Product:
                return eventProduct->getProductId();
            case Column::Tags: {
                return QString();
            }
            default:
                break;
        }

        Q_ASSERT(false);
        return QStringLiteral("Unknown Data");
    }

    enum class ItemType { Root, Event, EventProduct };
    ItemType indexItemType(const QModelIndex &index) const
    {

        if (!index.isValid()) {
            return ItemType::Root;
        }
        else if (index.internalPointer() == nullptr) {
            return ItemType::Event;
        }
        else {
            return ItemType::EventProduct;
        }
    }

    std::shared_ptr<DBEventProduct> getEventProduct(const QModelIndex &index)
    {
        auto event = static_cast<DBEvent *>(index.internalPointer());
        return m_EventProducts.at(event).value(index.row());
    }
};

CatalogueEventsModel::CatalogueEventsModel(QObject *parent)
        : QAbstractItemModel(parent),
          impl{spimpl::make_unique_impl<CatalogueEventsTableModelPrivate>()}
{
}

void CatalogueEventsModel::setEvents(const QVector<std::shared_ptr<DBEvent> > &events)
{
    beginResetModel();

    impl->m_Events = events;
    for (auto event : events) {
        impl->parseEventProduct(event);
    }

    endResetModel();
}

std::shared_ptr<DBEvent> CatalogueEventsModel::getEvent(int row) const
{
    return impl->m_Events.value(row);
}

void CatalogueEventsModel::addEvent(const std::shared_ptr<DBEvent> &event)
{
    beginInsertRows(QModelIndex(), impl->m_Events.count() - 1, impl->m_Events.count() - 1);
    impl->m_Events.append(event);
    impl->parseEventProduct(event);
    endInsertRows();
}

void CatalogueEventsModel::removeEvent(const std::shared_ptr<DBEvent> &event)
{
    auto index = impl->m_Events.indexOf(event);
    if (index >= 0) {
        beginRemoveRows(QModelIndex(), index, index);
        impl->m_Events.removeAt(index);
        impl->m_EventProducts.erase(event.get());
        endRemoveRows();
    }
}

void CatalogueEventsModel::refreshEvent(const std::shared_ptr<DBEvent> &event)
{
    auto eventIndex = impl->m_Events.indexOf(event);
    if (eventIndex >= 0) {
        emit dataChanged(index(eventIndex, 0), index(eventIndex, columnCount()));
    }
}

QModelIndex CatalogueEventsModel::index(int row, int column, const QModelIndex &parent) const
{
    if (!hasIndex(row, column, parent)) {
        return QModelIndex();
    }

    switch (impl->indexItemType(parent)) {
        case CatalogueEventsTableModelPrivate::ItemType::Root:
            return createIndex(row, column);
        case CatalogueEventsTableModelPrivate::ItemType::Event: {
            auto event = getEvent(parent.row());
            return createIndex(row, column, event.get());
        }
        case CatalogueEventsTableModelPrivate::ItemType::EventProduct:
            break;
        default:
            break;
    }

    return QModelIndex();
}

QModelIndex CatalogueEventsModel::parent(const QModelIndex &index) const
{
    switch (impl->indexItemType(index)) {
        case CatalogueEventsTableModelPrivate::ItemType::EventProduct: {
            auto parentEvent = static_cast<DBEvent *>(index.internalPointer());
            auto it
                = std::find_if(impl->m_Events.cbegin(), impl->m_Events.cend(),
                               [parentEvent](auto event) { return event.get() == parentEvent; });

            if (it != impl->m_Events.cend()) {
                return createIndex(it - impl->m_Events.cbegin(), 0);
            }
            else {
                return QModelIndex();
            }
        }
        case CatalogueEventsTableModelPrivate::ItemType::Root:
            break;
        case CatalogueEventsTableModelPrivate::ItemType::Event:
            break;
        default:
            break;
    }

    return QModelIndex();
}

int CatalogueEventsModel::rowCount(const QModelIndex &parent) const
{
    if (parent.column() > 0) {
        return 0;
    }

    switch (impl->indexItemType(parent)) {
        case CatalogueEventsTableModelPrivate::ItemType::Root:
            return impl->m_Events.count();
        case CatalogueEventsTableModelPrivate::ItemType::Event: {
            auto event = getEvent(parent.row());
            return impl->m_EventProducts[event.get()].count();
        }
        case CatalogueEventsTableModelPrivate::ItemType::EventProduct:
            break;
        default:
            break;
    }

    return 0;
}

int CatalogueEventsModel::columnCount(const QModelIndex &parent) const
{
    return static_cast<int>(CatalogueEventsTableModelPrivate::Column::NbColumn);
}

Qt::ItemFlags CatalogueEventsModel::flags(const QModelIndex &index) const
{
    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
}

QVariant CatalogueEventsModel::data(const QModelIndex &index, int role) const
{
    if (index.isValid()) {

        auto type = impl->indexItemType(index);
        if (type == CatalogueEventsTableModelPrivate::ItemType::Event) {
            auto event = getEvent(index.row());
            switch (role) {
                case Qt::DisplayRole:
                    return impl->eventData(index.column(), event);
                    break;
            }
        }
        else if (type == CatalogueEventsTableModelPrivate::ItemType::EventProduct) {
            auto product = impl->getEventProduct(index);
            switch (role) {
                case Qt::DisplayRole:
                    return impl->eventProductData(index.column(), product);
                    break;
            }
        }
    }

    return QVariant{};
}

QVariant CatalogueEventsModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole) {
        return impl->columnNames().value(section);
    }

    return QVariant();
}

void CatalogueEventsModel::sort(int column, Qt::SortOrder order)
{
    std::sort(impl->m_Events.begin(), impl->m_Events.end(),
              [this, column, order](auto e1, auto e2) {
                  auto data1 = impl->eventData(column, e1);
                  auto data2 = impl->eventData(column, e2);

                  auto result = data1.toString() < data2.toString();

                  return order == Qt::AscendingOrder ? result : !result;
              });

    emit dataChanged(QModelIndex(), QModelIndex());
}

Qt::DropActions CatalogueEventsModel::supportedDragActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

QStringList CatalogueEventsModel::mimeTypes() const
{
    return {MIME_TYPE_EVENT_LIST, MIME_TYPE_TIME_RANGE};
}

QMimeData *CatalogueEventsModel::mimeData(const QModelIndexList &indexes) const
{
    auto mimeData = new QMimeData;

    QVector<std::shared_ptr<DBEvent> > eventList;

    SqpRange firstTimeRange;
    for (const auto &index : indexes) {
        if (index.column() == 0) { // only the first column
            auto event = getEvent(index.row());
            if (eventList.isEmpty()) {
                // Gets the range of the first variable
                // firstTimeRange.m_TStart = event->getTStart();
                // firstTimeRange.m_TEnd = event->getTEnd();
            }

            eventList << event;
        }
    }

    auto eventsEncodedData
        = QByteArray{}; // sqpApp->catalogueController().->mimeDataForEvents(eventList); //TODO
    mimeData->setData(MIME_TYPE_EVENT_LIST, eventsEncodedData);

    if (eventList.count() == 1) {
        // No time range MIME data if multiple events are dragged
        auto timeEncodedData = TimeController::mimeDataForTimeRange(firstTimeRange);
        mimeData->setData(MIME_TYPE_TIME_RANGE, timeEncodedData);
    }

    return mimeData;
}
