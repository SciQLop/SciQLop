#ifndef SCIQLOP_REMOVEVARIABLEOPERATION_H
#define SCIQLOP_REMOVEVARIABLEOPERATION_H

#include "Visualization/IVisualizationWidgetVisitor.h"

#include <Common/spimpl.h>

#include <QLoggingCategory>

#include <memory>

class Variable2;

Q_DECLARE_LOGGING_CATEGORY(LOG_RemoveVariableOperation)

/**
 * @brief The RemoveVariableOperation class defines an operation that traverses all of visualization
 * widgets to remove a variable if they contain it
 */
class RemoveVariableOperation : public IVisualizationWidgetVisitor
{
public:
    /**
     * Ctor
     * @param variable the variable to remove from widgets
     */
    explicit RemoveVariableOperation(std::shared_ptr<Variable2> variable);

    void visitEnter(VisualizationWidget* widget) override final;
    void visitLeave(VisualizationWidget* widget) override final;
    void visitEnter(VisualizationTabWidget* tabWidget) override final;
    void visitLeave(VisualizationTabWidget* tabWidget) override final;
    void visitEnter(VisualizationZoneWidget* zoneWidget) override final;
    void visitLeave(VisualizationZoneWidget* zoneWidget) override final;
    void visit(VisualizationGraphWidget* graphWidget) override final;

private:
    class RemoveVariableOperationPrivate;
    spimpl::unique_impl_ptr<RemoveVariableOperationPrivate> impl;
};

#endif // SCIQLOP_REMOVEVARIABLEOPERATION_H
