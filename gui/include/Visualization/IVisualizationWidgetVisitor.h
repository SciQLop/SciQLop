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

    virtual void visitEnter(VisualizationWidget *widget) = 0;
    virtual void visitLeave(VisualizationWidget *widget) = 0;
    virtual void visitEnter(VisualizationTabWidget *tabWidget) = 0;
    virtual void visitLeave(VisualizationTabWidget *tabWidget) = 0;
    virtual void visitEnter(VisualizationZoneWidget *zoneWidget) = 0;
    virtual void visitLeave(VisualizationZoneWidget *zoneWidget) = 0;
    virtual void visit(VisualizationGraphWidget *graphWidget) = 0;
};


#endif // SCIQLOP_IVISUALIZATIONWIDGETVISITOR_H
