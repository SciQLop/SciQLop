#include "Catalogue/CatalogueTreeWidgetItem.h"
#include <Catalogue/CatalogueExplorerHelper.h>

#include <Catalogue/CatalogueController.h>
#include <SqpApplication.h>

#include <memory>

#include <DBCatalogue.h>

/// Column in the tree widget where the apply and cancel buttons must appear
const auto APPLY_CANCEL_BUTTONS_COLUMN = 1;

struct CatalogueTreeWidgetItem::CatalogueTreeWidgetItemPrivate {

    std::shared_ptr<DBCatalogue> m_Catalogue;

    CatalogueTreeWidgetItemPrivate(std::shared_ptr<DBCatalogue> catalogue) : m_Catalogue(catalogue)
    {
    }
};


CatalogueTreeWidgetItem::CatalogueTreeWidgetItem(std::shared_ptr<DBCatalogue> catalogue, int type)
        : QTreeWidgetItem(type),
          impl{spimpl::make_unique_impl<CatalogueTreeWidgetItemPrivate>(catalogue)}
{
    setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsEditable);
}

QVariant CatalogueTreeWidgetItem::data(int column, int role) const
{
    if (column == 0) {
        switch (role) {
            case Qt::EditRole: // fallthrough
            case Qt::DisplayRole:
                return impl->m_Catalogue->getName();
            default:
                break;
        }
    }

    return QTreeWidgetItem::data(column, role);
}

void CatalogueTreeWidgetItem::setData(int column, int role, const QVariant &value)
{
    if (role == Qt::EditRole && column == 0) {
        auto newName = value.toString();
        if (newName != impl->m_Catalogue->getName()) {
            setText(0, newName);
            impl->m_Catalogue->setName(newName);
            sqpApp->catalogueController().updateCatalogue(impl->m_Catalogue);
            setHasChanges(true);
        }
    }
    else {
        QTreeWidgetItem::setData(column, role, value);
    }
}

std::shared_ptr<DBCatalogue> CatalogueTreeWidgetItem::catalogue() const
{
    return impl->m_Catalogue;
}

void CatalogueTreeWidgetItem::setHasChanges(bool value)
{
    if (value) {
        if (!hasChanges()) {
            auto widget = CatalogueExplorerHelper::buildValidationWidget(
                treeWidget(), [this]() { setHasChanges(false); },
                [this]() { setHasChanges(false); });
            treeWidget()->setItemWidget(this, APPLY_CANCEL_BUTTONS_COLUMN, widget);
        }
    }
    else {
        // Note: the widget is destroyed
        treeWidget()->setItemWidget(this, APPLY_CANCEL_BUTTONS_COLUMN, nullptr);
    }
}

bool CatalogueTreeWidgetItem::hasChanges()
{
    return treeWidget()->itemWidget(this, APPLY_CANCEL_BUTTONS_COLUMN) != nullptr;
}

void CatalogueTreeWidgetItem::refresh()
{
    emitDataChanged();
}
