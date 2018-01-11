#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"
#include <SqpApplication.h>

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueExplorerHelper.h>
#include <Catalogue/CatalogueTreeItems/CatalogueTextTreeItem.h>
#include <Catalogue/CatalogueTreeItems/CatalogueTreeItem.h>
#include <Catalogue/CatalogueTreeModel.h>
#include <CatalogueDao.h>
#include <Common/MimeTypesDef.h>
#include <ComparaisonPredicate.h>
#include <DBCatalogue.h>

#include <QKeyEvent>
#include <QMenu>
#include <QMessageBox>
#include <QMimeData>

Q_LOGGING_CATEGORY(LOG_CatalogueSideBarWidget, "CatalogueSideBarWidget")


constexpr auto ALL_EVENT_ITEM_TYPE = CatalogueAbstractTreeItem::DEFAULT_TYPE + 1;
constexpr auto TRASH_ITEM_TYPE = CatalogueAbstractTreeItem::DEFAULT_TYPE + 2;
constexpr auto CATALOGUE_ITEM_TYPE = CatalogueAbstractTreeItem::DEFAULT_TYPE + 3;
constexpr auto DATABASE_ITEM_TYPE = CatalogueAbstractTreeItem::DEFAULT_TYPE + 4;

const auto DEFAULT_CATALOGUE_NAME = QObject::tr("Catalogue");


struct CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate {

    CatalogueTreeModel *m_TreeModel = nullptr;

    void configureTreeWidget(QTreeView *treeView);
    QModelIndex addDatabaseItem(const QString &name);
    CatalogueAbstractTreeItem *getDatabaseItem(const QString &name);
    CatalogueAbstractTreeItem *addCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue,
                                                const QModelIndex &databaseIndex);

    CatalogueTreeItem *getCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue) const;
    void setHasChanges(bool value, const QModelIndex &index, CatalogueSideBarWidget *sideBarWidget);
    bool hasChanges(const QModelIndex &index, QTreeView *treeView);

    int selectionType(QTreeView *treeView) const
    {
        auto selectedItems = treeView->selectionModel()->selectedRows();
        if (selectedItems.isEmpty()) {
            return CatalogueAbstractTreeItem::DEFAULT_TYPE;
        }
        else {
            auto firstIndex = selectedItems.first();
            auto firstItem = m_TreeModel->item(firstIndex);
            if (!firstItem) {
                Q_ASSERT(false);
                return CatalogueAbstractTreeItem::DEFAULT_TYPE;
            }
            auto selectionType = firstItem->type();

            for (auto itemIndex : selectedItems) {
                auto item = m_TreeModel->item(itemIndex);
                if (!item || item->type() != selectionType) {
                    // Incoherent multi selection
                    selectionType = CatalogueAbstractTreeItem::DEFAULT_TYPE;
                    break;
                }
            }

            return selectionType;
        }
    }

    QVector<std::shared_ptr<DBCatalogue> > selectedCatalogues(QTreeView *treeView) const
    {
        QVector<std::shared_ptr<DBCatalogue> > catalogues;
        auto selectedItems = treeView->selectionModel()->selectedRows();
        for (auto itemIndex : selectedItems) {
            auto item = m_TreeModel->item(itemIndex);
            if (item && item->type() == CATALOGUE_ITEM_TYPE) {
                catalogues.append(static_cast<CatalogueTreeItem *>(item)->catalogue());
            }
        }

        return catalogues;
    }

    QStringList selectedRepositories(QTreeView *treeView) const
    {
        QStringList repositories;
        auto selectedItems = treeView->selectionModel()->selectedRows();
        for (auto itemIndex : selectedItems) {
            auto item = m_TreeModel->item(itemIndex);
            if (item && item->type() == DATABASE_ITEM_TYPE) {
                repositories.append(item->text());
            }
        }

        return repositories;
    }
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
    emit catalogueListChanged();

    ui->treeView->header()->setStretchLastSection(false);
    ui->treeView->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->treeView->header()->setSectionResizeMode((int)CatalogueTreeModel::Column::Name,
                                                 QHeaderView::Stretch);

    connect(ui->treeView, &QTreeView::clicked, this, &CatalogueSideBarWidget::emitSelection);
    connect(ui->treeView->selectionModel(), &QItemSelectionModel::currentChanged, this,
            &CatalogueSideBarWidget::emitSelection);


    connect(ui->btnAdd, &QToolButton::clicked, [this]() {
        auto catalogue = std::make_shared<DBCatalogue>();
        catalogue->setName(DEFAULT_CATALOGUE_NAME);
        sqpApp->catalogueController().addCatalogue(catalogue);
        auto item = this->addCatalogue(catalogue, REPOSITORY_DEFAULT);
        this->setCatalogueChanges(catalogue, true);
        ui->treeView->edit(impl->m_TreeModel->indexOf(item));

    });


    connect(impl->m_TreeModel, &CatalogueTreeModel::itemDropped,
            [this](auto index, auto mimeData, auto action) {
                auto item = impl->m_TreeModel->item(index);

                if (item && item->type() == CATALOGUE_ITEM_TYPE) {
                    auto catalogue = static_cast<CatalogueTreeItem *>(item)->catalogue();
                    this->setCatalogueChanges(catalogue, true);
                }

                if (action == Qt::MoveAction) {
                    /// Display a save button on source catalogues
                    auto sourceCatalogues = sqpApp->catalogueController().cataloguesForMimeData(
                        mimeData->data(MIME_TYPE_SOURCE_CATALOGUE_LIST));
                    for (auto catalogue : sourceCatalogues) {
                        if (auto catalogueItem = impl->getCatalogueItem(catalogue)) {
                            catalogueItem->replaceCatalogue(catalogue);
                            this->setCatalogueChanges(catalogue, true);
                        }
                    }

                    this->emitSelection();
                }
            });

    connect(ui->btnRemove, &QToolButton::clicked, [this]() {
        QVector<QPair<std::shared_ptr<DBCatalogue>, CatalogueAbstractTreeItem *> >
            cataloguesToItems;
        auto selectedIndexes = ui->treeView->selectionModel()->selectedRows();

        for (auto index : selectedIndexes) {
            auto item = impl->m_TreeModel->item(index);
            if (item && item->type() == CATALOGUE_ITEM_TYPE) {
                auto catalogue = static_cast<CatalogueTreeItem *>(item)->catalogue();
                cataloguesToItems << qMakePair(catalogue, item);
            }
        }

        if (!cataloguesToItems.isEmpty()) {

            if (QMessageBox::warning(this, tr("Remove Catalogue(s)"),
                                     tr("The selected catalogues(s) will be completly removed "
                                        "from the repository!\nAre you sure you want to continue?"),
                                     QMessageBox::Yes | QMessageBox::No, QMessageBox::No)
                == QMessageBox::Yes) {

                for (auto catalogueToItem : cataloguesToItems) {
                    sqpApp->catalogueController().removeCatalogue(catalogueToItem.first);
                    impl->m_TreeModel->removeChildItem(
                        catalogueToItem.second,
                        impl->m_TreeModel->indexOf(catalogueToItem.second->parent()));
                }
                emitSelection();
                emit catalogueListChanged();
            }
        }
    });

    connect(impl->m_TreeModel, &CatalogueTreeModel::itemRenamed, [this](auto index) {
        auto selectedIndexes = ui->treeView->selectionModel()->selectedRows();
        if (selectedIndexes.contains(index)) {
            this->emitSelection();
        }
        impl->setHasChanges(true, index, this);
        emit this->catalogueListChanged();
    });

    ui->treeView->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->treeView, &QTreeView::customContextMenuRequested, this,
            &CatalogueSideBarWidget::onContextMenuRequested);
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
}

CatalogueAbstractTreeItem *
CatalogueSideBarWidget::addCatalogue(const std::shared_ptr<DBCatalogue> &catalogue,
                                     const QString &repository)
{
    auto repositoryItem = impl->getDatabaseItem(repository);
    auto catalogueItem
        = impl->addCatalogueItem(catalogue, impl->m_TreeModel->indexOf(repositoryItem));

    emit catalogueListChanged();

    return catalogueItem;
}

void CatalogueSideBarWidget::setCatalogueChanges(const std::shared_ptr<DBCatalogue> &catalogue,
                                                 bool hasChanges)
{
    if (auto catalogueItem = impl->getCatalogueItem(catalogue)) {
        auto index = impl->m_TreeModel->indexOf(catalogueItem);
        impl->setHasChanges(hasChanges, index, this);
        // catalogueItem->refresh();
    }
}

QVector<std::shared_ptr<DBCatalogue> >
CatalogueSideBarWidget::getCatalogues(const QString &repository) const
{
    QVector<std::shared_ptr<DBCatalogue> > result;
    auto repositoryItem = impl->getDatabaseItem(repository);
    for (auto child : repositoryItem->children()) {
        if (child->type() == CATALOGUE_ITEM_TYPE) {
            auto catalogueItem = static_cast<CatalogueTreeItem *>(child);
            result << catalogueItem->catalogue();
        }
        else {
            qCWarning(LOG_CatalogueSideBarWidget()) << "getCatalogues: invalid structure";
        }
    }

    return result;
}

void CatalogueSideBarWidget::emitSelection()
{
    auto selectionType = impl->selectionType(ui->treeView);

    switch (selectionType) {
        case CATALOGUE_ITEM_TYPE:
            emit this->catalogueSelected(impl->selectedCatalogues(ui->treeView));
            break;
        case DATABASE_ITEM_TYPE:
            emit this->databaseSelected(impl->selectedRepositories(ui->treeView));
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
    auto allEventsItem = new CatalogueTextTreeItem{QIcon{":/icones/allEvents.png"}, "All Events",
                                                   ALL_EVENT_ITEM_TYPE};
    auto allEventIndex = m_TreeModel->addTopLevelItem(allEventsItem);
    treeView->setCurrentIndex(allEventIndex);

    auto trashItem
        = new CatalogueTextTreeItem{QIcon{":/icones/trash.png"}, "Trash", TRASH_ITEM_TYPE};
    m_TreeModel->addTopLevelItem(trashItem);

    auto separator = new QFrame{treeView};
    separator->setFrameShape(QFrame::HLine);
    auto separatorItem
        = new CatalogueTextTreeItem{QIcon{}, QString{}, CatalogueAbstractTreeItem::DEFAULT_TYPE};
    separatorItem->setEnabled(false);
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
    auto databaseItem
        = new CatalogueTextTreeItem{QIcon{":/icones/database.png"}, {name}, DATABASE_ITEM_TYPE};
    auto databaseIndex = m_TreeModel->addTopLevelItem(databaseItem);

    return databaseIndex;
}

CatalogueAbstractTreeItem *
CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getDatabaseItem(const QString &name)
{
    for (auto item : m_TreeModel->topLevelItems()) {
        if (item->type() == DATABASE_ITEM_TYPE && item->text() == name) {
            return item;
        }
    }

    return nullptr;
}

CatalogueAbstractTreeItem *CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::addCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue, const QModelIndex &databaseIndex)
{
    auto catalogueItem
        = new CatalogueTreeItem{catalogue, QIcon{":/icones/catalogue.png"}, CATALOGUE_ITEM_TYPE};
    m_TreeModel->addChildItem(catalogueItem, databaseIndex);

    return catalogueItem;
}

CatalogueTreeItem *CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue) const
{
    for (auto item : m_TreeModel->topLevelItems()) {
        if (item->type() == DATABASE_ITEM_TYPE) {
            for (auto childItem : item->children()) {
                if (childItem->type() == CATALOGUE_ITEM_TYPE) {
                    auto catalogueItem = static_cast<CatalogueTreeItem *>(childItem);
                    if (catalogueItem->catalogue()->getUniqId() == catalogue->getUniqId()) {
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

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::setHasChanges(
    bool value, const QModelIndex &index, CatalogueSideBarWidget *sideBarWidget)
{
    std::shared_ptr<DBCatalogue> catalogue = nullptr;
    auto item = m_TreeModel->item(index);
    if (item && item->type() == CATALOGUE_ITEM_TYPE) {
        catalogue = static_cast<CatalogueTreeItem *>(item)->catalogue();
    }

    auto validationIndex = index.sibling(index.row(), (int)CatalogueTreeModel::Column::Validation);
    if (value) {
        if (!hasChanges(validationIndex, sideBarWidget->ui->treeView)) {
            auto widget = CatalogueExplorerHelper::buildValidationWidget(
                sideBarWidget->ui->treeView,
                [this, validationIndex, sideBarWidget, catalogue]() {
                    if (catalogue) {
                        sqpApp->catalogueController().saveCatalogue(catalogue);
                        emit sideBarWidget->catalogueSaved(catalogue);
                    }
                    setHasChanges(false, validationIndex, sideBarWidget);
                },
                [this, validationIndex, sideBarWidget, catalogue, item]() {
                    if (catalogue) {
                        bool removed;
                        sqpApp->catalogueController().discardCatalogue(catalogue, removed);

                        if (removed) {
                            m_TreeModel->removeChildItem(item,
                                                         m_TreeModel->indexOf(item->parent()));
                        }
                        else {
                            m_TreeModel->refresh(m_TreeModel->indexOf(item));
                            setHasChanges(false, validationIndex, sideBarWidget);
                        }
                        sideBarWidget->emitSelection();
                    }
                });
            sideBarWidget->ui->treeView->setIndexWidget(validationIndex, widget);
            sideBarWidget->ui->treeView->header()->resizeSection(
                (int)CatalogueTreeModel::Column::Validation, QHeaderView::ResizeToContents);
        }
    }
    else {
        // Note: the widget is destroyed
        sideBarWidget->ui->treeView->setIndexWidget(validationIndex, nullptr);
    }
}

bool CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::hasChanges(const QModelIndex &index,
                                                                       QTreeView *treeView)
{
    auto validationIndex = index.sibling(index.row(), (int)CatalogueTreeModel::Column::Validation);
    return treeView->indexWidget(validationIndex) != nullptr;
}


void CatalogueSideBarWidget::keyPressEvent(QKeyEvent *event)
{
    switch (event->key()) {
        case Qt::Key_Delete: {
            ui->btnRemove->click();
        }
        default:
            break;
    }
}
