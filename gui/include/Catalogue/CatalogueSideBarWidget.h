#ifndef CATALOGUESIDEBARWIDGET_H
#define CATALOGUESIDEBARWIDGET_H

#include <QWidget>

namespace Ui {
class CatalogueSideBarWidget;
}

class CatalogueSideBarWidget : public QWidget {
    Q_OBJECT

public:
    explicit CatalogueSideBarWidget(QWidget *parent = 0);
    ~CatalogueSideBarWidget();

private:
    Ui::CatalogueSideBarWidget *ui;
};

#endif // CATALOGUESIDEBARWIDGET_H
