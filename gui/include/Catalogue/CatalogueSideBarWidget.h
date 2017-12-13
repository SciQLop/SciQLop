#ifndef SCIQLOP_CATALOGUESIDEBARWIDGET_H
#define SCIQLOP_CATALOGUESIDEBARWIDGET_H

#include <Common/spimpl.h>
#include <QTreeWidgetItem>
#include <QWidget>

class DBCatalogue;

namespace Ui {
class CatalogueSideBarWidget;
}

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

private:
    Ui::CatalogueSideBarWidget *ui;

    class CatalogueSideBarWidgetPrivate;
    spimpl::unique_impl_ptr<CatalogueSideBarWidgetPrivate> impl;

private slots:
    void onContextMenuRequested(const QPoint &pos);
};

#endif // SCIQLOP_CATALOGUESIDEBARWIDGET_H
