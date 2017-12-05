#include "Visualization/VisualizationSelectionZoneManager.h"
#include "Visualization/VisualizationSelectionZoneItem.h"

struct VisualizationSelectionZoneManager::VisualizationSelectionZoneManagerPrivate {
    QVector<VisualizationSelectionZoneItem *> m_SelectedItems;
};

VisualizationSelectionZoneManager::VisualizationSelectionZoneManager()
        : impl{spimpl::make_unique_impl<VisualizationSelectionZoneManagerPrivate>()}
{
}

void VisualizationSelectionZoneManager::select(
    const QVector<VisualizationSelectionZoneItem *> &items)
{
    clearSelection();
    for (auto item : items) {
        setSelected(item, true);
    }
}

void VisualizationSelectionZoneManager::setSelected(VisualizationSelectionZoneItem *item,
                                                    bool value)
{
    if (value != item->selected()) {
        item->setSelected(value);
        item->parentPlot()->replot();
    }

    if (!value && impl->m_SelectedItems.contains(item)) {
        impl->m_SelectedItems.removeAll(item);
    }
    else if (value) {
        impl->m_SelectedItems << item;
    }
}

void VisualizationSelectionZoneManager::clearSelection()
{
    for (auto item : impl->m_SelectedItems) {
        item->setSelected(false);
        item->parentPlot()->replot();
    }

    impl->m_SelectedItems.clear();
}

QVector<VisualizationSelectionZoneItem *> VisualizationSelectionZoneManager::selectedItems() const
{
    return impl->m_SelectedItems;
}
