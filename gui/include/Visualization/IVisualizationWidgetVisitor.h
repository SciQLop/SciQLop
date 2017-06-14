#ifndef SCIQLOP_IVISUALIZATIONWIDGETVISITOR_H
#define SCIQLOP_IVISUALIZATIONWIDGETVISITOR_H


class VisualizationWidget;
class VisualizationTabWidget;
class VisualizationZoneWidget;
class VisualizationGraphWidget;

/**
 * @brief The IVisualizationWidgetVisitor handles the visualization widget vistor pattern.
 */
class IVisualizationWidgetVisitor {

public:
    virtual ~IVisualizationWidgetVisitor() = default;

    virtual void visit(VisualizationWidget *widget) = 0;
    virtual void visit(VisualizationTabWidget *tabWidget) = 0;
    virtual void visit(VisualizationZoneWidget *zoneWidget) = 0;
    virtual void visit(VisualizationGraphWidget *graphWidget) = 0;
};


#endif // SCIQLOP_IVISUALIZATIONWIDGETVISITOR_H
