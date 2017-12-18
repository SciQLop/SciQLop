#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"
#include <SqpApplication.h>

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueExplorerHelper.h>
#include <Catalogue/CatalogueTreeModel.h>
#include <Catalogue/CatalogueTreeWidgetItem.h>
#include <CatalogueDao.h>
#include <ComparaisonPredicate.h>
#include <DBCatalogue.h>

#include <QMenu>

Q_LOGGING_CATEGORY(LOG_CatalogueSideBarWidget, "CatalogueSideBarWidget")


constexpr auto ALL_EVENT_ITEM_TYPE = QTreeWidgetItem::UserType;
constexpr auto TRASH_ITEM_TYPE = QTreeWidgetItem::UserType + 1;
constexpr auto CATALOGUE_ITEM_TYPE = QTreeWidgetItem::UserType + 2;
constexpr auto DATABASE_ITEM_TYPE = QTreeWidgetItem::UserType + 3;


struct CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate {

    CatalogueTreeModel *m_TreeModel = nullptr;

    void configureTreeWidget(QTreeView *treeView);
    QModelIndex addDatabaseItem(const QString &name);
    QTreeWidgetItem *getDatabaseItem(const QString &name);
    void addCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue,
                          const QModelIndex &databaseIndex);

    CatalogueTreeWidgetItem *getCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue) const;
    void setHasChanges(bool value, const QModelIndex &index, QTreeView *treeView);
    bool hasChanges(const QModelIndex &index, QTreeView *treeView);
};

CatalogueSideBarWidget::CatalogueSideBarWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueSideBarWidget),
          impl{spimpl::make_unique_impl<CatalogueSideBarWidgetPrivate>()}
{
    ui->setupUi(this);

    impl->m_TreeModel = new CatalogueTreeModel(this);
    ui->treeView->setModel(impl->m_TreeModel);

    impl->configureTreeWidget(ui->treeView);

    ui->treeView->header()->setStretchLastSection(false);
    ui->treeView->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->treeView->header()->setSectionResizeMode(0, QHeaderView::Stretch);

    auto emitSelection = [this]() {

        auto selectedItems = ui->treeView->selectionModel()->selectedRows();
        if (selectedItems.isEmpty()) {
            emit this->selectionCleared();
        }
        else {
            QVector<std::shared_ptr<DBCatalogue> > catalogues;
            QStringList databases;
            auto firstIndex = selectedItems.first();
            auto firstItem = impl->m_TreeModel->item(firstIndex);
            if (!firstItem) {
                Q_ASSERT(false);
                return;
            }
            auto selectionType = firstItem->type();

            for (auto itemIndex : selectedItems) {
                auto item = impl->m_TreeModel->item(itemIndex);
                if (item && item->type() == selectionType) {
                    switch (selectionType) {
                        case CATALOGUE_ITEM_TYPE:
                            catalogues.append(
                                static_cast<CatalogueTreeWidgetItem *>(item)->catalogue());
                            break;
                        case DATABASE_ITEM_TYPE:
                            selectionType = DATABASE_ITEM_TYPE;
                            databases.append(item->text(0));
                        case ALL_EVENT_ITEM_TYPE: // fallthrough
                        case TRASH_ITEM_TYPE:     // fallthrough
                        default:
                            break;
                    }
                }
                else {
                    // Incoherent multi selection
                    selectionType = -1;
                    break;
                }
            }

            switch (selectionType) {
                case CATALOGUE_ITEM_TYPE:
                    emit this->catalogueSelected(catalogues);
                    break;
                case DATABASE_ITEM_TYPE:
                    emit this->databaseSelected(databases);
                    break;
                case ALL_EVENT_ITEM_TYPE:
                    emit this->allEventsSelected();
                    break;
                case TRASH_ITEM_TYPE:
                    emit this->trashSelected();
                    break;
                default:
                    emit this->selectionCleared();
                    break;
            }
        }


    };

    connect(ui->treeView, &QTreeView::clicked, emitSelection);
    connect(ui->treeView->selectionModel(), &QItemSelectionModel::currentChanged, emitSelection);
    connect(impl->m_TreeModel, &CatalogueTreeModel::itemRenamed, [emitSelection, this](auto index) {
        auto selectedIndexes = ui->treeView->selectionModel()->selectedRows();
        if (selectedIndexes.contains(index)) {
            emitSelection();
        }

        auto item = impl->m_TreeModel->item(index);
        impl->setHasChanges(true, index, ui->treeView);
    });

    ui->treeView->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->treeView, &QTreeWidget::customContextMenuRequested, this,
            &CatalogueSideBarWidget::onContextMenuRequested);
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
}

void CatalogueSideBarWidget::setCatalogueChanges(const std::shared_ptr<DBCatalogue> &catalogue,
                                                 bool hasChanges)
{
    if (auto catalogueItem = impl->getCatalogueItem(catalogue)) {
        auto index = impl->m_TreeModel->indexOf(catalogueItem);
        impl->setHasChanges(hasChanges, index, ui->treeView);
        catalogueItem->refresh();
    }
}

void CatalogueSideBarWidget::onContextMenuRequested(const QPoint &pos)
{
    QMenu menu{this};

    auto currentIndex = ui->treeView->currentIndex();
    auto currentItem = impl->m_TreeModel->item(currentIndex);
    if (!currentItem) {
        return;
    }

    switch (currentItem->type()) {
        case CATALOGUE_ITEM_TYPE:
            menu.addAction("Rename", [this, currentIndex]() { ui->treeView->edit(currentIndex); });
            break;
        case DATABASE_ITEM_TYPE:
            break;
        case ALL_EVENT_ITEM_TYPE:
            break;
        case TRASH_ITEM_TYPE:
            menu.addAction("Empty Trash", []() {
                // TODO
            });
            break;
        default:
            break;
    }

    if (!menu.isEmpty()) {
        menu.exec(ui->treeView->mapToGlobal(pos));
    }
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::configureTreeWidget(QTreeView *treeView)
{
    auto allEventsItem = new QTreeWidgetItem{{"All Events"}, ALL_EVENT_ITEM_TYPE};
    allEventsItem->setIcon(0, QIcon(":/icones/allEvents.png"));
    m_TreeModel->addTopLevelItem(allEventsItem);

    auto trashItem = new QTreeWidgetItem{{"Trash"}, TRASH_ITEM_TYPE};
    trashItem->setIcon(0, QIcon(":/icones/trash.png"));
    m_TreeModel->addTopLevelItem(trashItem);

    auto separator = new QFrame{treeView};
    separator->setFrameShape(QFrame::HLine);
    auto separatorItem = new QTreeWidgetItem{};
    separatorItem->setFlags(Qt::NoItemFlags);
    auto separatorIndex = m_TreeModel->addTopLevelItem(separatorItem);
    treeView->setIndexWidget(separatorIndex, separator);

    auto repositories = sqpApp->catalogueController().getRepositories();
    for (auto dbname : repositories) {
        auto dbIndex = addDatabaseItem(dbname);
        auto catalogues = sqpApp->catalogueController().retrieveCatalogues(dbname);
        for (auto catalogue : catalogues) {
            addCatalogueItem(catalogue, dbIndex);
        }
    }

    treeView->expandAll();
}

QModelIndex
CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::addDatabaseItem(const QString &name)
{
    auto databaseItem = new QTreeWidgetItem{{name}, DATABASE_ITEM_TYPE};
    databaseItem->setIcon(0, QIcon{":/icones/database.png"});
    auto databaseIndex = m_TreeModel->addTopLevelItem(databaseItem);

    return databaseIndex;
}

QTreeWidgetItem *
CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getDatabaseItem(const QString &name)
{
    for (auto i = 0; i < m_TreeModel->topLevelItemCount(); ++i) {
        auto item = m_TreeModel->topLevelItem(i);
        if (item->type() == DATABASE_ITEM_TYPE && item->text(0) == name) {
            return item;
        }
    }

    return nullptr;
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::addCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue, const QModelIndex &databaseIndex)
{
    auto catalogueItem = new CatalogueTreeWidgetItem{catalogue, CATALOGUE_ITEM_TYPE};
    catalogueItem->setIcon(0, QIcon{":/icones/catalogue.png"});
    m_TreeModel->addChildItem(catalogueItem, databaseIndex);
}

CatalogueTreeWidgetItem *CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue) const
{
    for (auto i = 0; i < m_TreeModel->topLevelItemCount(); ++i) {
        auto item = m_TreeModel->topLevelItem(i);
        if (item->type() == DATABASE_ITEM_TYPE) {
            for (auto j = 0; j < item->childCount(); ++j) {
                auto childItem = item->child(j);
                if (childItem->type() == CATALOGUE_ITEM_TYPE) {
                    auto catalogueItem = static_cast<CatalogueTreeWidgetItem *>(childItem);
                    if (catalogueItem->catalogue() == catalogue) {
                        return catalogueItem;
                    }
                }
                else {
                    qCWarning(LOG_CatalogueSideBarWidget()) << "getCatalogueItem: Invalid tree "
                                                               "structure. A database item should "
                                                               "only contain catalogues.";
                    Q_ASSERT(false);
                }
            }
        }
    }

    return nullptr;
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::setHasChanges(bool value,
                                                                          const QModelIndex &index,
                                                                          QTreeView *treeView)
{
    auto validationIndex = index.sibling(index.row(), (int)CatalogueTreeModel::Column::Validation);
    if (value) {
        if (!hasChanges(validationIndex, treeView)) {
            auto widget = CatalogueExplorerHelper::buildValidationWidget(
                treeView,
                [this, validationIndex, treeView]() {
                    setHasChanges(false, validationIndex, treeView);
                },
                [this, validationIndex, treeView]() {
                    setHasChanges(false, validationIndex, treeView);
                });
            treeView->setIndexWidget(validationIndex, widget);
        }
    }
    else {
        // Note: the widget is destroyed
        treeView->setIndexWidget(validationIndex, nullptr);
    }
}

bool CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::hasChanges(const QModelIndex &index,
                                                                       QTreeView *treeView)
{
    auto validationIndex = index.sibling(index.row(), (int)CatalogueTreeModel::Column::Validation);
    return treeView->indexWidget(validationIndex) != nullptr;
}
