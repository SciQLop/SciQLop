#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"
#include <SqpApplication.h>

#include <Catalogue/CatalogueController.h>
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

    void configureTreeWidget(QTreeWidget *treeWidget);
    QTreeWidgetItem *addDatabaseItem(const QString &name, QTreeWidget *treeWidget);
    QTreeWidgetItem *getDatabaseItem(const QString &name, QTreeWidget *treeWidget);
    void addCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue,
                          QTreeWidgetItem *parentDatabaseItem);

    CatalogueTreeWidgetItem *getCatalogueItem(const std::shared_ptr<DBCatalogue> &catalogue,
                                              QTreeWidget *treeWidget) const;
};

CatalogueSideBarWidget::CatalogueSideBarWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueSideBarWidget),
          impl{spimpl::make_unique_impl<CatalogueSideBarWidgetPrivate>()}
{
    ui->setupUi(this);
    impl->configureTreeWidget(ui->treeWidget);

    ui->treeWidget->setColumnCount(2);
    ui->treeWidget->header()->setStretchLastSection(false);
    ui->treeWidget->header()->setSectionResizeMode(QHeaderView::ResizeToContents);
    ui->treeWidget->header()->setSectionResizeMode(0, QHeaderView::Stretch);

    auto emitSelection = [this]() {

        auto selectedItems = ui->treeWidget->selectedItems();
        if (selectedItems.isEmpty()) {
            emit this->selectionCleared();
        }
        else {
            QVector<std::shared_ptr<DBCatalogue> > catalogues;
            QStringList databases;
            int selectionType = selectedItems.first()->type();

            for (auto item : ui->treeWidget->selectedItems()) {
                if (item->type() == selectionType) {
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

    connect(ui->treeWidget, &QTreeWidget::itemClicked, emitSelection);
    connect(ui->treeWidget, &QTreeWidget::currentItemChanged, emitSelection);
    connect(ui->treeWidget, &QTreeWidget::itemChanged,
            [emitSelection, this](auto item, auto column) {
                auto selectedItems = ui->treeWidget->selectedItems();
                qDebug() << "ITEM CHANGED" << column;
                if (selectedItems.contains(item) && column == 0) {
                    emitSelection();
                }
            });

    ui->treeWidget->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(ui->treeWidget, &QTreeWidget::customContextMenuRequested, this,
            &CatalogueSideBarWidget::onContextMenuRequested);
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
}

void CatalogueSideBarWidget::setCatalogueChanges(const std::shared_ptr<DBCatalogue> &catalogue,
                                                 bool hasChanges)
{
    if (auto catalogueItem = impl->getCatalogueItem(catalogue, ui->treeWidget)) {
        catalogueItem->setHasChanges(hasChanges);
        catalogueItem->refresh();
    }
}

void CatalogueSideBarWidget::onContextMenuRequested(const QPoint &pos)
{
    QMenu menu{this};

    auto currentItem = ui->treeWidget->currentItem();
    switch (currentItem->type()) {
        case CATALOGUE_ITEM_TYPE:
            menu.addAction("Rename",
                           [this, currentItem]() { ui->treeWidget->editItem(currentItem); });
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
        menu.exec(ui->treeWidget->mapToGlobal(pos));
    }
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::configureTreeWidget(
    QTreeWidget *treeWidget)
{
    auto allEventsItem = new QTreeWidgetItem{{"All Events"}, ALL_EVENT_ITEM_TYPE};
    allEventsItem->setIcon(0, QIcon(":/icones/allEvents.png"));
    treeWidget->addTopLevelItem(allEventsItem);

    auto trashItem = new QTreeWidgetItem{{"Trash"}, TRASH_ITEM_TYPE};
    trashItem->setIcon(0, QIcon(":/icones/trash.png"));
    treeWidget->addTopLevelItem(trashItem);

    auto separator = new QFrame{treeWidget};
    separator->setFrameShape(QFrame::HLine);
    auto separatorItem = new QTreeWidgetItem{};
    separatorItem->setFlags(Qt::NoItemFlags);
    treeWidget->addTopLevelItem(separatorItem);
    treeWidget->setItemWidget(separatorItem, 0, separator);

    auto repositories = sqpApp->catalogueController().getRepositories();
    for (auto dbname : repositories) {
        auto db = addDatabaseItem(dbname, treeWidget);

        auto catalogues = sqpApp->catalogueController().retrieveCatalogues(dbname);
        for (auto catalogue : catalogues) {
            addCatalogueItem(catalogue, db);
        }
    }

    treeWidget->expandAll();
}

QTreeWidgetItem *
CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::addDatabaseItem(const QString &name,
                                                                       QTreeWidget *treeWidget)
{
    auto databaseItem = new QTreeWidgetItem{{name}, DATABASE_ITEM_TYPE};
    databaseItem->setIcon(0, QIcon{":/icones/database.png"});
    treeWidget->addTopLevelItem(databaseItem);

    return databaseItem;
}

QTreeWidgetItem *
CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getDatabaseItem(const QString &name,
                                                                       QTreeWidget *treeWidget)
{
    for (auto i = 0; i < treeWidget->topLevelItemCount(); ++i) {
        auto item = treeWidget->topLevelItem(i);
        if (item->type() == DATABASE_ITEM_TYPE && item->text(0) == name) {
            return item;
        }
    }

    return nullptr;
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::addCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue, QTreeWidgetItem *parentDatabaseItem)
{
    auto catalogueItem = new CatalogueTreeWidgetItem{catalogue, CATALOGUE_ITEM_TYPE};
    catalogueItem->setIcon(0, QIcon{":/icones/catalogue.png"});
    parentDatabaseItem->addChild(catalogueItem);
}

CatalogueTreeWidgetItem *CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::getCatalogueItem(
    const std::shared_ptr<DBCatalogue> &catalogue, QTreeWidget *treeWidget) const
{
    for (auto i = 0; i < treeWidget->topLevelItemCount(); ++i) {
        auto item = treeWidget->topLevelItem(i);
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
