#include "Visualization/operations/GenerateVariableMenuOperation.h"

#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"

#include <Variable/Variable.h>

#include <QMenu>

struct GenerateVariableMenuOperation::GenerateVariableMenuOperationPrivate {
    explicit GenerateVariableMenuOperationPrivate(QMenu *menu, std::shared_ptr<Variable> variable)
            : m_Variable{variable}
    {
    }

    std::shared_ptr<Variable> m_Variable;
};

GenerateVariableMenuOperation::GenerateVariableMenuOperation(QMenu *menu,
                                                             std::shared_ptr<Variable> variable)
        : impl{spimpl::make_unique_impl<GenerateVariableMenuOperationPrivate>(menu, variable)}
{
}

void GenerateVariableMenuOperation::visitEnter(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to accommodate a variable
    Q_UNUSED(widget)
}

void GenerateVariableMenuOperation::visitLeave(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to accommodate a variable
    Q_UNUSED(widget)
}

void GenerateVariableMenuOperation::visitEnter(VisualizationTabWidget *tabWidget)
{
    /// @todo ALX
}

void GenerateVariableMenuOperation::visitLeave(VisualizationTabWidget *tabWidget)
{
    /// @todo ALX
}

void GenerateVariableMenuOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    /// @todo ALX
}

void GenerateVariableMenuOperation::visitLeave(VisualizationZoneWidget *zoneWidget)
{
    /// @todo ALX
}

void GenerateVariableMenuOperation::visit(VisualizationGraphWidget *graphWidget)
{
    /// @todo ALX
}
