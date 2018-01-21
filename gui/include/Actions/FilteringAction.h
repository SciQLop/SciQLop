#ifndef SCIQLOP_FILTERINGACTION_H
#define SCIQLOP_FILTERINGACTION_H

#include <Common/spimpl.h>
#include <QWidgetAction>

/// A LineEdit inside an action which is able to filter other actions
class FilteringAction : public QWidgetAction {
public:
    FilteringAction(QWidget *parent);

    void addActionToFilter(QAction *action);

private:
    class FilteringActionPrivate;
    spimpl::unique_impl_ptr<FilteringActionPrivate> impl;
};

#endif // SCIQLOP_FILTERINGACTION_H
