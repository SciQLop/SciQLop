#include "Visualization/operations/FindVariableOperation.h"

#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationWidget.h"
#include "Visualization/VisualizationZoneWidget.h"

#include <Variable/Variable.h>

struct FindVariableOperation::FindVariableOperationPrivate {
    explicit FindVariableOperationPrivate(std::shared_ptr<Variable> variable) : m_Variable{variable}
    {
    }

    void visit(IVisualizationWidget *widget)
    {
        if (m_Variable && widget && widget->contains(*m_Variable)) {
            m_Containers.insert(widget);
        }
    }

    std::shared_ptr<Variable> m_Variable;          ///< Variable to find
    std::set<IVisualizationWidget *> m_Containers; ///< Containers found for the variable
};

FindVariableOperation::FindVariableOperation(std::shared_ptr<Variable> variable)
        : impl{spimpl::make_unique_impl<FindVariableOperationPrivate>(variable)}
{
}

void FindVariableOperation::visitEnter(VisualizationWidget *widget)
{
    impl->visit(widget);
}

void FindVariableOperation::visitLeave(VisualizationWidget *widget)
{
    // Does nothing
    Q_UNUSED(widget);
}

void FindVariableOperation::visitEnter(VisualizationTabWidget *tabWidget)
{
    impl->visit(tabWidget);
}

void FindVariableOperation::visitLeave(VisualizationTabWidget *tabWidget)
{
    // Does nothing
    Q_UNUSED(tabWidget);
}

void FindVariableOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    impl->visit(zoneWidget);
}

void FindVariableOperation::visitLeave(VisualizationZoneWidget *zoneWidget)
{
    // Does nothing
    Q_UNUSED(zoneWidget);
}

void FindVariableOperation::visit(VisualizationGraphWidget *graphWidget)
{
    impl->visit(graphWidget);
}

std::set<IVisualizationWidget *> FindVariableOperation::result() const noexcept
{
    return impl->m_Containers;
}
