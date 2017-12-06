#include "Catalogue/CatalogueSideBarWidget.h"
#include "ui_CatalogueSideBarWidget.h"

auto ALL_EVENT_ITEM_TYPE = QTreeWidgetItem::UserType;
auto TRASH_ITEM_TYPE = QTreeWidgetItem::UserType + 1;
auto CATALOGUE_ITEM_TYPE = QTreeWidgetItem::UserType + 2;
auto DATABASE_ITEM_TYPE = QTreeWidgetItem::UserType + 3;


struct CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate {
    void configureTreeWidget(QTreeWidget *treeWidget);
};

CatalogueSideBarWidget::CatalogueSideBarWidget(QWidget *parent)
        : QWidget(parent),
          ui(new Ui::CatalogueSideBarWidget),
          impl{spimpl::make_unique_impl<CatalogueSideBarWidgetPrivate>()}
{
    ui->setupUi(this);
    impl->configureTreeWidget(ui->treeWidget);
}

CatalogueSideBarWidget::~CatalogueSideBarWidget()
{
    delete ui;
}

void CatalogueSideBarWidget::CatalogueSideBarWidgetPrivate::configureTreeWidget(
    QTreeWidget *treeWidget)
{
    auto allEventsItem = new QTreeWidgetItem({"All Events"}, ALL_EVENT_ITEM_TYPE);
    allEventsItem->setIcon(0, QIcon(":/icones/allEvents.png"));
    treeWidget->addTopLevelItem(allEventsItem);

    auto trashItem = new QTreeWidgetItem({"Trash"}, TRASH_ITEM_TYPE);
    trashItem->setIcon(0, QIcon(":/icones/trash.png"));
    treeWidget->addTopLevelItem(trashItem);

    auto separator = new QFrame(treeWidget);
    separator->setFrameShape(QFrame::HLine);

    auto separatorItem = new QTreeWidgetItem();
    separatorItem->setFlags(Qt::NoItemFlags);
    treeWidget->addTopLevelItem(separatorItem);
    treeWidget->setItemWidget(separatorItem, 0, separator);
}
