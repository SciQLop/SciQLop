#ifndef SCIQLOP_VISUALIZATIONSELECTIONZONEMANAGER_H
#define SCIQLOP_VISUALIZATIONSELECTIONZONEMANAGER_H

#include <Common/spimpl.h>

#include <QVector>

class VisualizationSelectionZoneItem;

class VisualizationSelectionZoneManager {
public:
    VisualizationSelectionZoneManager();

    void select(const QVector<VisualizationSelectionZoneItem *> &items);
    void setSelected(VisualizationSelectionZoneItem *item, bool value);

    void clearSelection();

    QVector<VisualizationSelectionZoneItem *> selectedItems() const;

private:
    class VisualizationSelectionZoneManagerPrivate;
    spimpl::unique_impl_ptr<VisualizationSelectionZoneManagerPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONSELECTIONZONEMANAGER_H
