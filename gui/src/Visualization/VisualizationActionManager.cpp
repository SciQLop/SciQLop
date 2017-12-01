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
    actionController.addSectionZoneAction("Align Left", [](auto &zones) {});
    actionController.addSectionZoneAction("Align Right", [](auto &zones) {});
}
