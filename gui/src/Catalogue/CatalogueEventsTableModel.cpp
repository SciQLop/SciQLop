#include "Catalogue/CatalogueEventsTableModel.h"

#include <Common/DateUtils.h>
#include <Common/MimeTypesDef.h>
#include <DBEvent.h>
#include <DBTag.h>
#include <Data/SqpRange.h>
#include <QMimeData>
#include <SqpApplication.h>
#include <Time/TimeController.h>

struct CatalogueEventsTableModel::CatalogueEventsTableModelPrivate {
    QVector<DBEvent> m_Events;

    enum class Column { Event, TStart, TEnd, Tags, Product, NbColumn };
    QStringList columnNames()
    {
        return QStringList{tr("Event"), tr("TStart"), tr("TEnd"), tr("Tags"), tr("Product")};
    }

    QVariant eventData(int col, const DBEvent &event) const
    {
        switch (static_cast<Column>(col)) {
            case Column::Event:
                return event.getName();
            case Column::TStart:
                return DateUtils::dateTime(event.getTStart());
            case Column::TEnd:
                return DateUtils::dateTime(event.getTEnd());
            case Column::Product:
                return event.getProduct();
            case Column::Tags: {
                QString tagList;
                auto tags = const_cast<DBEvent *>(&event)->getTags();
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
};

CatalogueEventsTableModel::CatalogueEventsTableModel(QObject *parent)
        : QAbstractTableModel(parent),
          impl{spimpl::make_unique_impl<CatalogueEventsTableModelPrivate>()}
{
}

void CatalogueEventsTableModel::setEvents(const QVector<DBEvent> &events)
{
    beginResetModel();
    impl->m_Events = events;
    endResetModel();
}

DBEvent CatalogueEventsTableModel::getEvent(int row) const
{
    return impl->m_Events.value(row);
}

int CatalogueEventsTableModel::rowCount(const QModelIndex &parent) const
{
    int r = impl->m_Events.count();
    return r;
}

int CatalogueEventsTableModel::columnCount(const QModelIndex &parent) const
{
    int c = static_cast<int>(CatalogueEventsTableModelPrivate::Column::NbColumn);
    return c;
}

Qt::ItemFlags CatalogueEventsTableModel::flags(const QModelIndex &index) const
{
    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsDragEnabled;
}

QVariant CatalogueEventsTableModel::data(const QModelIndex &index, int role) const
{
    if (index.isValid()) {
        auto event = getEvent(index.row());

        switch (role) {
            case Qt::DisplayRole:
                return impl->eventData(index.column(), event);
                break;
        }
    }

    return QVariant{};
}

QVariant CatalogueEventsTableModel::headerData(int section, Qt::Orientation orientation,
                                               int role) const
{
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole) {
        return impl->columnNames().value(section);
    }

    return QVariant();
}

void CatalogueEventsTableModel::sort(int column, Qt::SortOrder order)
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

Qt::DropActions CatalogueEventsTableModel::supportedDragActions() const
{
    return Qt::CopyAction | Qt::MoveAction;
}

QStringList CatalogueEventsTableModel::mimeTypes() const
{
    return {MIME_TYPE_EVENT_LIST, MIME_TYPE_TIME_RANGE};
}

QMimeData *CatalogueEventsTableModel::mimeData(const QModelIndexList &indexes) const
{
    auto mimeData = new QMimeData;

    QVector<DBEvent> eventList;

    SqpRange firstTimeRange;
    for (const auto &index : indexes) {
        if (index.column() == 0) { // only the first column
            auto event = getEvent(index.row());
            if (eventList.isEmpty()) {
                // Gets the range of the first variable
                firstTimeRange.m_TStart = event.getTStart();
                firstTimeRange.m_TEnd = event.getTEnd();
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
