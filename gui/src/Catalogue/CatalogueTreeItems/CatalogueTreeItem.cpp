#include "Catalogue/CatalogueTreeItems/CatalogueTreeItem.h"
#include <Catalogue/CatalogueExplorerHelper.h>

#include <Catalogue/CatalogueController.h>
#include <Common/MimeTypesDef.h>
#include <QIcon>
#include <QMimeData>
#include <SqpApplication.h>

#include <memory>

#include <DBCatalogue.h>

struct CatalogueTreeItem::CatalogueTreeItemPrivate {

    std::shared_ptr<DBCatalogue> m_Catalogue;
    QIcon m_Icon;

    CatalogueTreeItemPrivate(std::shared_ptr<DBCatalogue> catalogue, const QIcon &icon)
            : m_Catalogue(catalogue), m_Icon(icon)
    {
    }
};


CatalogueTreeItem::CatalogueTreeItem(std::shared_ptr<DBCatalogue> catalogue, const QIcon &icon,
                                     int type)
        : CatalogueAbstractTreeItem(type),
          impl{spimpl::make_unique_impl<CatalogueTreeItemPrivate>(catalogue, icon)}
{
}

QVariant CatalogueTreeItem::data(int column, int role) const
{
    if (column == 0) {
        switch (role) {
            case Qt::EditRole: // fallthrough
            case Qt::DisplayRole:
                return impl->m_Catalogue->getName();
            case Qt::DecorationRole:
                return impl->m_Icon;
            default:
                break;
        }
    }

    return QVariant();
}

bool CatalogueTreeItem::setData(int column, int role, const QVariant &value)
{
    bool result = false;

    if (role == Qt::EditRole && column == 0) {
        auto newName = value.toString();
        if (newName != impl->m_Catalogue->getName()) {
            impl->m_Catalogue->setName(newName);
            sqpApp->catalogueController().updateCatalogue(impl->m_Catalogue);
            result = true;
        }
    }

    return result;
}

Qt::ItemFlags CatalogueTreeItem::flags(int column) const
{
    if (column == 0) {
        return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsEditable
               | Qt::ItemIsDropEnabled;
    }
    else {
        return Qt::ItemIsEnabled | Qt::ItemIsSelectable;
    }
}

bool CatalogueTreeItem::canDropMimeData(const QMimeData *data, Qt::DropAction action)
{
    // Check that the event is not dropped on the same catalogue
    auto sourceCatalogues = sqpApp->catalogueController().cataloguesForMimeData(
        data->data(MIME_TYPE_SOURCE_CATALOGUE_LIST));
    for (auto catalogue : sourceCatalogues) {
        if (catalogue->getUniqId() == impl->m_Catalogue->getUniqId()) {
            return false;
        }
    }

    auto events = sqpApp->catalogueController().eventsForMimeData(data->data(MIME_TYPE_EVENT_LIST));
    auto canDrop = data->hasFormat(MIME_TYPE_EVENT_LIST);

    for (auto event : events) {
        canDrop &= (event->getRepository() == impl->m_Catalogue->getRepository());
    }

    return canDrop;
}

bool CatalogueTreeItem::dropMimeData(const QMimeData *data, Qt::DropAction action)
{
    Q_ASSERT(canDropMimeData(data, action));
    // Warning: Check that the events aren't already in the catalogue
    // No need to check check for the repository: inter-repository drop is forbidden in
    // canDropMimeData

    auto events = sqpApp->catalogueController().eventsForMimeData(data->data(MIME_TYPE_EVENT_LIST));
    auto sourceCatalogues = sqpApp->catalogueController().cataloguesForMimeData(
        data->data(MIME_TYPE_SOURCE_CATALOGUE_LIST));

    for (auto event : events) {

        if (action == Qt::MoveAction) {
            for (auto catalogue : sourceCatalogues) {
                catalogue->removeEvent(event->getUniqId());
                sqpApp->catalogueController().updateCatalogue(catalogue);
            }
        }

        impl->m_Catalogue->addEvent(event->getUniqId());
        sqpApp->catalogueController().updateCatalogue(impl->m_Catalogue);
    }
}

std::shared_ptr<DBCatalogue> CatalogueTreeItem::catalogue() const
{
    return impl->m_Catalogue;
}
