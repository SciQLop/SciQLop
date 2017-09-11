#ifndef SCIQLOP_IGRAPHSYNCHRONIZER_H
#define SCIQLOP_IGRAPHSYNCHRONIZER_H

class VisualizationGraphWidget;

/**
 * @brief The IVisualizationSynchronizer interface represents a delegate used to manage the
 * synchronization between graphs, applying them processes or properties to ensure their
 * synchronization
 */
class IGraphSynchronizer {

public:
    virtual ~IGraphSynchronizer() = default;

    /**
     * Adds a graph as a new synchronized element, and sets its properties so that its
     * synchronization is maintained with all other graphs managed by the synchonizer
     * @param graph the graph to add in the synchronization
     */
    virtual void addGraph(VisualizationGraphWidget &graph) const = 0;
};

#endif // SCIQLOP_IGRAPHSYNCHRONIZER_H
