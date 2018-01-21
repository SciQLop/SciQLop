#include "Actions/FilteringAction.h"

#include <QLineEdit>

struct FilteringAction::FilteringActionPrivate {
    QLineEdit *m_FilterLineEdit;
    QVector<QAction *> m_FilteredActions;
};

FilteringAction::FilteringAction(QWidget *parent)
        : QWidgetAction(parent), impl{spimpl::make_unique_impl<FilteringActionPrivate>()}
{
    impl->m_FilterLineEdit = new QLineEdit(parent);
    setDefaultWidget(impl->m_FilterLineEdit);

    connect(impl->m_FilterLineEdit, &QLineEdit::textEdited, [this](auto text) {
        for (auto action : impl->m_FilteredActions) {
            auto match = action->text().contains(text, Qt::CaseInsensitive);
            action->setVisible(match);
        }
    });
}

void FilteringAction::addActionToFilter(QAction *action)
{
    impl->m_FilteredActions << action;
}
