#include "Visualization/VisualizationActionManager.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationSelectionZoneItem.h"

#include <Actions/ActionsGuiController.h>
#include <SqpApplication.h>

VisualizationActionManager::VisualizationActionManager() {}

void VisualizationActionManager::installSelectionZoneActions()
{
    auto &actionController = sqpApp->actionsGuiController();

    auto removeZonesAction
        = actionController.addSectionZoneAction("Remove Selected Zone(s)", [](auto zones) {
              for (auto selectionZone : zones) {
                  if (auto graph = selectionZone->parentGraphWidget()) {
                      graph->removeSelectionZone(selectionZone);
                  }
              }
          });
    removeZonesAction->setDisplayedShortcut(QKeySequence::Delete);

    auto alignEnableFuntion = [](auto items) { return items.count() > 1; };

    // Vertical alignment actions
    auto alignLeftAction
        = actionController.addSectionZoneAction("Align Vertically / Left", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesVerticallyOnLeft(zones, false);
          });
    alignLeftAction->setEnableFunction(alignEnableFuntion);

    auto alignLeftBorderAction
        = actionController.addSectionZoneAction("Align Vertically / Left Borders", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesVerticallyOnLeft(zones, true);
          });
    alignLeftBorderAction->setEnableFunction(alignEnableFuntion);

    auto alignRightAction
        = actionController.addSectionZoneAction("Align Vertically / Right", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesVerticallyOnRight(zones, false);
          });
    alignRightAction->setEnableFunction(alignEnableFuntion);

    auto alignRightBorderAction
        = actionController.addSectionZoneAction("Align Vertically / Right Borders", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesVerticallyOnRight(zones, true);
          });
    alignRightBorderAction->setEnableFunction(alignEnableFuntion);

    auto alignLeftAndRightAction = actionController.addSectionZoneAction(
        "Align Vertically / Left and Right", [](auto zones) {
            Q_ASSERT(zones.count() > 1);
            auto ref = zones.takeFirst();
            ref->alignZonesVerticallyOnLeft(zones, false);
            ref->alignZonesVerticallyOnRight(zones, true);
        });
    alignLeftAndRightAction->setEnableFunction(alignEnableFuntion);

    // Temporal alignment actions
    auto alignLeftTemporallyAction
        = actionController.addSectionZoneAction("Align Temporally / Left", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesTemporallyOnLeft(zones, false);
          });
    alignLeftTemporallyAction->setEnableFunction(alignEnableFuntion);

    auto alignLeftBorderTemporallyAction
        = actionController.addSectionZoneAction("Align Temporally / Left Borders", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesTemporallyOnLeft(zones, true);
          });
    alignLeftBorderTemporallyAction->setEnableFunction(alignEnableFuntion);

    auto alignRightTemporallyAction
        = actionController.addSectionZoneAction("Align Temporally / Right", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesTemporallyOnRight(zones, false);
          });
    alignRightTemporallyAction->setEnableFunction(alignEnableFuntion);

    auto alignRightBorderTemporallyAction
        = actionController.addSectionZoneAction("Align Temporally / Right Borders", [](auto zones) {
              Q_ASSERT(zones.count() > 1);
              auto ref = zones.takeFirst();
              ref->alignZonesTemporallyOnRight(zones, true);
          });
    alignRightBorderTemporallyAction->setEnableFunction(alignEnableFuntion);

    auto alignLeftAndRightTemporallyAction = actionController.addSectionZoneAction(
        "Align Temporally / Left and Right", [](auto zones) {
            Q_ASSERT(zones.count() > 1);
            auto ref = zones.takeFirst();
            ref->alignZonesTemporallyOnLeft(zones, false);
            ref->alignZonesTemporallyOnRight(zones, true);
        });
    alignLeftAndRightTemporallyAction->setEnableFunction(alignEnableFuntion);
}
