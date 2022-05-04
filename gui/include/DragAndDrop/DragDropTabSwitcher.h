#ifndef SCIQLOP_DRAGDROPTABSWITCHER_H
#define SCIQLOP_DRAGDROPTABSWITCHER_H

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QTabBar>

Q_DECLARE_LOGGING_CATEGORY(LOG_DragDropTabSwitcher)

class DragDropTabSwitcher : public QObject {
    Q_OBJECT

public:
    DragDropTabSwitcher(QObject *parent = nullptr);

    void addTabBar(QTabBar *tabBar);
    void removeTabBar(QTabBar *tabBar);

protected:
    bool eventFilter(QObject *obj, QEvent *event) override;

private:
    class DragDropTabSwitcherPrivate;
    spimpl::unique_impl_ptr<DragDropTabSwitcherPrivate> impl;
};


#endif // SCIQLOP_DRAGDROPTABSWITCHER_H
