#include "Visualization/VisualizationActionManager.h"

#include <Actions/ActionsGuiController.h>
#include <SqpApplication.h>

VisualizationActionManager::VisualizationActionManager() {}

void VisualizationActionManager::installSelectionZoneActions()
{
    auto &actionController = sqpApp->actionsGuiController();
    actionController.addSectionZoneAction("Remove Selected Zone(s)", [](auto &zone) {});
    actionController.addSectionZoneAction("Align Left", [](auto &zone) {});
    actionController.addSectionZoneAction("Align Right", [](auto &zone) {});
}
