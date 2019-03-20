#ifndef SCIQLOP_FINDVARIABLEOPERATION_H
#define SCIQLOP_FINDVARIABLEOPERATION_H

#include "Visualization/IVisualizationWidgetVisitor.h"

#include <Common/spimpl.h>

#include <set>

class IVisualizationWidget;
class Variable2;

/**
 * @brief The FindVariableOperation class defines an operation that traverses all of visualization
 * widgets to determine which ones contain the variable passed as parameter. The result of the
 * operation is the list of widgets that contain the variable.
 */
class FindVariableOperation : public IVisualizationWidgetVisitor
{
public:
    /**
     * Ctor
     * @param variable the variable to find
     */
    explicit FindVariableOperation(std::shared_ptr<Variable2> variable);

    void visitEnter(VisualizationWidget* widget) override final;
    void visitLeave(VisualizationWidget* widget) override final;
    void visitEnter(VisualizationTabWidget* tabWidget) override final;
    void visitLeave(VisualizationTabWidget* tabWidget) override final;
    void visitEnter(VisualizationZoneWidget* zoneWidget) override final;
    void visitLeave(VisualizationZoneWidget* zoneWidget) override final;
    void visit(VisualizationGraphWidget* graphWidget) override final;

    /// @return the widgets that contain the variable
    std::set<IVisualizationWidget*> result() const noexcept;

private:
    class FindVariableOperationPrivate;
    spimpl::unique_impl_ptr<FindVariableOperationPrivate> impl;
};

#endif // SCIQLOP_FINDVARIABLEOPERATION_H
