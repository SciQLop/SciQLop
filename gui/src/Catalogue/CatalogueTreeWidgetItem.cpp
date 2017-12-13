#include "Catalogue/CatalogueTreeWidgetItem.h"

#include <memory>

#include <QBoxLayout>
#include <QToolButton>

const auto VALIDATION_BUTTON_ICON_SIZE = 12;

struct CatalogueTreeWidgetItem::CatalogueTreeWidgetItemPrivate {

    DBCatalogue m_Catalogue;

    CatalogueTreeWidgetItemPrivate(DBCatalogue catalogue) : m_Catalogue(catalogue) {}
};


CatalogueTreeWidgetItem::CatalogueTreeWidgetItem(DBCatalogue catalogue, int type)
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
                return impl->m_Catalogue.getName();
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
        if (newName != impl->m_Catalogue.getName()) {
            setText(0, newName);
            impl->m_Catalogue.setName(newName);
            setHasChanges(true);
        }
    }
    else {
        QTreeWidgetItem::setData(column, role, value);
    }
}

DBCatalogue CatalogueTreeWidgetItem::catalogue() const
{
    return impl->m_Catalogue;
}

void CatalogueTreeWidgetItem::setHasChanges(bool value)
{
    if (value) {
        auto widet = new QWidget{treeWidget()};

        auto layout = new QHBoxLayout{widet};
        layout->setContentsMargins(0, 0, 0, 0);
        layout->setSpacing(0);

        auto btnValid = new QToolButton{widet};
        btnValid->setIcon(QIcon{":/icones/save"});
        btnValid->setIconSize(QSize{VALIDATION_BUTTON_ICON_SIZE, VALIDATION_BUTTON_ICON_SIZE});
        btnValid->setAutoRaise(true);
        QObject::connect(btnValid, &QToolButton::clicked, [this]() { setHasChanges(false); });
        layout->addWidget(btnValid);

        auto btnDiscard = new QToolButton{widet};
        btnDiscard->setIcon(QIcon{":/icones/discard"});
        btnDiscard->setIconSize(QSize{VALIDATION_BUTTON_ICON_SIZE, VALIDATION_BUTTON_ICON_SIZE});
        btnDiscard->setAutoRaise(true);
        QObject::connect(btnDiscard, &QToolButton::clicked, [this]() { setHasChanges(false); });
        layout->addWidget(btnDiscard);

        treeWidget()->setItemWidget(this, 1, {widet});
        treeWidget()->resizeColumnToContents(1);
    }
    else {
        // Note: the widget is destroyed
        treeWidget()->setItemWidget(this, 1, nullptr);
    }
}
