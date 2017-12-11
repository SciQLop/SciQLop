#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"
#include <SqpApplication.h>

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueTreeWidgetItem.h>
#include <CatalogueDao.h>
#include <ComparaisonPredicate.h>
#include <DBCatalogue.h>


constexpr auto ALL_EVENT_ITEM_TYPE = QTreeWidgetItem::UserType;
constexpr auto TRASH_ITEM_TYPE = QTreeWidgetItem::UserType + 1;
constexpr auto CATALOGUE_ITEM_TYPE = QTreeWidgetItem::UserType + 2;
constexpr auto DATABASE_ITEM_TYPE = QTreeWidgetItem::UserType + 3;


struct CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate {

    QHash<QTreeWidgetItem *, DBCatalogue> m_CatalogueMap;

    void configureTreeWidget(QTreeWidget *treeWidget);
    QTreeWidgetItem *addDatabaseItem(const QString &name, QTreeWidget *treeWidget);
    QTreeWidgetItem *getDatabaseItem(const QString &name, QTreeWidget *treeWidget);
    void addCatalogueItem(const DBCatalogue &catalogue, QTreeWidgetItem *parentDatabaseItem);
};

CatalogueSideBarWidget::CatalogueSideBarWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueSideBarWidget),
          impl{spimpl::make_unique_impl<CatalogueSideBarWidgetPrivate>()}
{
    ui->setupUi(this);
    impl->configureTreeWidget(ui->treeWidget);

    auto emitSelection = [this]() {

        auto selectedItems = ui->treeWidget->selectedItems();
        if (selectedItems.isEmpty()) {
            emit this->selectionCleared();
        }
        else {
            QVector<DBCatalogue> catalogues;
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
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
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

    // Test
    auto &dao = sqpApp->catalogueController().getDao();
    auto allPredicate = std::make_shared<ComparaisonPredicate>(QString{"uniqId"}, "-1",
                                                               ComparaisonOperation::DIFFERENT);

    auto db = addDatabaseItem("Default", treeWidget);

    auto catalogues = dao.getCatalogues(allPredicate);
    for (auto catalogue : catalogues) {
        addCatalogueItem(catalogue, db);
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
    const DBCatalogue &catalogue, QTreeWidgetItem *parentDatabaseItem)
{
    auto catalogueItem = new CatalogueTreeWidgetItem{catalogue, CATALOGUE_ITEM_TYPE};
    catalogueItem->setIcon(0, QIcon{":/icones/catalogue.png"});
    parentDatabaseItem->addChild(catalogueItem);
}
