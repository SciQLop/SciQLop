#include "Visualization/VisualizationActionManager.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationSelectionZoneItem.h"

#include <Actions/ActionsGuiController.h>
#include <SqpApplication.h>

VisualizationActionManager::VisualizationActionManager() {}

void VisualizationActionManager::installSelectionZoneActions()
{
    auto &actionController = sqpApp->actionsGuiController();

    actionController.addSectionZoneAction("Remove Selected Zone(s)", [](auto &zones) {
        for (auto selectionZone : zones) {
            if (auto graph = selectionZone->parentGraphWidget()) {
                graph->removeSelectionZone(selectionZone);
            }
        }
    });

    auto alignEnableFuntion = [](auto &items) { return items.count() > 0; };

    auto alignLeftAction = actionController.addSectionZoneAction("Align Left Vertically", [](auto &zones) {});
    alignLeftAction->setEnableFunction(alignEnableFuntion);

    auto alignRightAction
        = actionController.addSectionZoneAction("Align Right vertically", [](auto &zones) {});
    alignRightAction->setEnableFunction(alignEnableFuntion);
}
