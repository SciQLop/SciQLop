#include "Actions/ActionsGuiController.h"

struct ActionsGuiController::ActionsGuiControllerPrivate {

    QVector<std::shared_ptr<SelectionZoneAction> > m_SelectionZoneActions;
    QSet<QStringList> m_FilteredMenu;
};

ActionsGuiController::ActionsGuiController()
        : impl{spimpl::make_unique_impl<ActionsGuiControllerPrivate>()}
{
}

std::shared_ptr<SelectionZoneAction>
ActionsGuiController::addSectionZoneAction(const QString &name,
                                           SelectionZoneAction::ExecuteFunction function)
{
    auto action = std::make_shared<SelectionZoneAction>(name, function);
    impl->m_SelectionZoneActions.push_back(action);

    return action;
}

std::shared_ptr<SelectionZoneAction>
ActionsGuiController::addSectionZoneAction(const QStringList &subMenuList, const QString &name,
                                           SelectionZoneAction::ExecuteFunction function)
{
    auto action = std::make_shared<SelectionZoneAction>(subMenuList, name, function);
    impl->m_SelectionZoneActions.push_back(action);

    return action;
}

QVector<std::shared_ptr<SelectionZoneAction> > ActionsGuiController::selectionZoneActions() const
{
    return impl->m_SelectionZoneActions;
}

void ActionsGuiController::removeAction(const std::shared_ptr<SelectionZoneAction> &action)
{
    impl->m_SelectionZoneActions.removeAll(action);
}

void ActionsGuiController::addFilterForMenu(const QStringList &menuPath)
{
    impl->m_FilteredMenu.insert(menuPath);
}

bool ActionsGuiController::isMenuFiltered(const QStringList &menuPath) const
{
    return impl->m_FilteredMenu.contains(menuPath);
}
