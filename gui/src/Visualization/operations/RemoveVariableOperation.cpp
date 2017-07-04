#include "Visualization/operations/RemoveVariableOperation.h"
#include "Visualization/VisualizationGraphWidget.h"

#include <Variable/Variable.h>

Q_LOGGING_CATEGORY(LOG_RemoveVariableOperation, "RemoveVariableOperation")

struct RemoveVariableOperation::RemoveVariableOperationPrivate {
    explicit RemoveVariableOperationPrivate(std::shared_ptr<Variable> variable)
            : m_Variable(variable)
    {
    }

    std::shared_ptr<Variable> m_Variable;
};

RemoveVariableOperation::RemoveVariableOperation(std::shared_ptr<Variable> variable)
        : impl{spimpl::make_unique_impl<RemoveVariableOperationPrivate>(variable)}
{
}

void RemoveVariableOperation::visitEnter(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to contain a variable
    Q_UNUSED(widget)
}

void RemoveVariableOperation::visitLeave(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to contain a variable
    Q_UNUSED(widget)
}

void RemoveVariableOperation::visitEnter(VisualizationTabWidget *tabWidget)
{
    // VisualizationTabWidget is not intended to contain a variable
    Q_UNUSED(tabWidget)
}

void RemoveVariableOperation::visitLeave(VisualizationTabWidget *tabWidget)
{
    // VisualizationTabWidget is not intended to contain a variable
    Q_UNUSED(tabWidget)
}

void RemoveVariableOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    // VisualizationZoneWidget is not intended to contain a variable
    Q_UNUSED(zoneWidget)
}

void RemoveVariableOperation::visitLeave(VisualizationZoneWidget *zoneWidget)
{
    // VisualizationZoneWidget is not intended to contain a variable
    Q_UNUSED(zoneWidget)
}

void RemoveVariableOperation::visit(VisualizationGraphWidget *graphWidget)
{
    if (graphWidget) {
        // If the widget contains the variable, removes it
        if (impl->m_Variable && graphWidget->contains(*impl->m_Variable)) {
            graphWidget->removeVariable(impl->m_Variable);
        }
    }
    else {
        qCCritical(LOG_RemoveVariableOperation(),
                   "Can't visit VisualizationGraphWidget : the widget is null");
    }
}
