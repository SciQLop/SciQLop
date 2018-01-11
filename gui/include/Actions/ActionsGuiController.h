#ifndef SCIQLOP_ACTIONSGUICONTROLLER_H
#define SCIQLOP_ACTIONSGUICONTROLLER_H

#include <Actions/SelectionZoneAction.h>
#include <Common/spimpl.h>

#include <memory>

class ActionsGuiController {
public:
    ActionsGuiController();

    std::shared_ptr<SelectionZoneAction>
    addSectionZoneAction(const QString &name, SelectionZoneAction::ExecuteFunction function);

    std::shared_ptr<SelectionZoneAction>
    addSectionZoneAction(const QStringList &subMenuList, const QString &name,
                         SelectionZoneAction::ExecuteFunction function);

    QVector<std::shared_ptr<SelectionZoneAction> > selectionZoneActions() const;

    void removeAction(const std::shared_ptr<SelectionZoneAction> &action);

private:
    class ActionsGuiControllerPrivate;
    spimpl::unique_impl_ptr<ActionsGuiControllerPrivate> impl;
};

#endif // SCIQLOP_ACTIONSGUICONTROLLER_H
