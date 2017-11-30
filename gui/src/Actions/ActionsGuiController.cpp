#include "Actions/ActionsGuiController.h"

struct ActionsGuiController::ActionsGuiControllerPrivate {

    QVector<std::shared_ptr<SelectionZoneAction> > m_SelectionZoneActions;
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

QVector<std::shared_ptr<SelectionZoneAction> > ActionsGuiController::selectionZoneActions() const
{
    return impl->m_SelectionZoneActions;
}
