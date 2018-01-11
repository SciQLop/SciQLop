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

    /// Sets a flag to say that the specified menu can be filtered, usually via a FilteringAction
    void addFilterForMenu(const QStringList &menuPath);

    /// Returns true if the menu can be filtered
    bool isMenuFiltered(const QStringList &menuPath) const;

private:
    class ActionsGuiControllerPrivate;
    spimpl::unique_impl_ptr<ActionsGuiControllerPrivate> impl;
};

#endif // SCIQLOP_ACTIONSGUICONTROLLER_H
