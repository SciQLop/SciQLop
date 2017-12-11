#ifndef SCIQLOP_CATALOGUESIDEBARWIDGET_H
#define SCIQLOP_CATALOGUESIDEBARWIDGET_H

#include <Common/spimpl.h>
#include <QTreeWidgetItem>
#include <QWidget>

#include <DBCatalogue.h>

namespace Ui {
class CatalogueSideBarWidget;
}

class CatalogueSideBarWidget : public QWidget {
    Q_OBJECT

signals:
    void catalogueSelected(const QVector<DBCatalogue> &catalogues);
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
};

#endif // SCIQLOP_CATALOGUESIDEBARWIDGET_H
