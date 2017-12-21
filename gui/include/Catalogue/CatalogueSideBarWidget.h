#ifndef SCIQLOP_CATALOGUESIDEBARWIDGET_H
#define SCIQLOP_CATALOGUESIDEBARWIDGET_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QTreeWidgetItem>
#include <QWidget>

class CatalogueAbstractTreeItem;
class DBCatalogue;

namespace Ui {
class CatalogueSideBarWidget;
}

Q_DECLARE_LOGGING_CATEGORY(LOG_CatalogueSideBarWidget)

class CatalogueSideBarWidget : public QWidget {
    Q_OBJECT

signals:
    void catalogueSelected(const QVector<std::shared_ptr<DBCatalogue> > &catalogues);
    void databaseSelected(const QStringList &databases);
    void allEventsSelected();
    void trashSelected();
    void selectionCleared();

public:
    explicit CatalogueSideBarWidget(QWidget *parent = 0);
    virtual ~CatalogueSideBarWidget();

    CatalogueAbstractTreeItem *addCatalogue(const std::shared_ptr<DBCatalogue> &catalogue,
                                            const QString &repository);
    void setCatalogueChanges(const std::shared_ptr<DBCatalogue> &catalogue, bool hasChanges);

    QVector<std::shared_ptr<DBCatalogue> > getCatalogues(const QString &repository) const;

private slots:
    void emitSelection();

private:
    Ui::CatalogueSideBarWidget *ui;

    class CatalogueSideBarWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueSideBarWidgetPrivate> impl;

private slots:
    void onContextMenuRequested(const QPoint &pos);
};

#endif // SCIQLOP_CATALOGUESIDEBARWIDGET_H
