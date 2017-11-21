#include "Visualization/operations/GenerateVariableMenuOperation.h"
#include "Visualization/operations/MenuBuilder.h"

#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"

#include <Variable/Variable.h>

#include <QMenu>
#include <QStack>

Q_LOGGING_CATEGORY(LOG_GenerateVariableMenuOperation, "GenerateVariableMenuOperation")

struct GenerateVariableMenuOperation::GenerateVariableMenuOperationPrivate {
    explicit GenerateVariableMenuOperationPrivate(
        QMenu *menu, std::shared_ptr<Variable> variable,
        std::set<IVisualizationWidget *> variableContainers)
            : m_Variable{variable},
              m_VariableContainers{std::move(variableContainers)},
              m_PlotMenuBuilder{menu},
              m_UnplotMenuBuilder{menu}
    {
    }

    void visitRootEnter()
    {
        // Creates the root menu
        if (auto plotMenu
            = m_PlotMenuBuilder.addMenu(QObject::tr("Plot"), QIcon{":/icones/plot.png"})) {
            plotMenu->setEnabled(m_Variable && m_Variable->dataSeries() != nullptr);
        }

        m_UnplotMenuBuilder.addMenu(QObject::tr("Unplot"), QIcon{":/icones/unplot.png"});
    }

    void visitRootLeave()
    {
        // Closes the root menu
        m_PlotMenuBuilder.closeMenu();
        m_UnplotMenuBuilder.closeMenu();
    }

    void visitNodeEnter(const IVisualizationWidget &container)
    {
        // Opens a new menu associated to the node
        m_PlotMenuBuilder.addMenu(container.name());
        m_UnplotMenuBuilder.addMenu(container.name());
    }

    template <typename ActionFun>
    void visitNodeLeavePlot(const IVisualizationWidget &container, const QString &actionName,
                            ActionFun actionFunction)
    {
        if (isValidContainer(container)) {
            m_PlotMenuBuilder.addSeparator();
            m_PlotMenuBuilder.addAction(actionName, actionFunction);
        }

        // Closes the menu associated to the node
        m_PlotMenuBuilder.closeMenu();
    }

    void visitNodeLeaveUnplot()
    {
        // Closes the menu associated to the node
        m_UnplotMenuBuilder.closeMenu();
    }

    template <typename ActionFun>
    void visitLeafPlot(const IVisualizationWidget &container, const QString &actionName,
                       ActionFun actionFunction)
    {
        if (isValidContainer(container)) {
            m_PlotMenuBuilder.addAction(actionName, actionFunction);
        }
    }

    template <typename ActionFun>
    void visitLeafUnplot(IVisualizationWidget *container, const QString &actionName,
                         ActionFun actionFunction)
    {
        // If the container contains the variable, we generate 'unplot' action
        if (m_VariableContainers.count(container) == 1) {
            m_UnplotMenuBuilder.addAction(actionName, actionFunction);
        }
    }

    bool isValidContainer(const IVisualizationWidget &container) const noexcept
    {
        // A container is valid if it can contain the variable and if the variable is not already
        // contained in another container
        return m_Variable && m_VariableContainers.size() == 0 && container.canDrop(*m_Variable);
    }

    std::shared_ptr<Variable> m_Variable;
    std::set<IVisualizationWidget *> m_VariableContainers;
    MenuBuilder m_PlotMenuBuilder;   ///< Builder for the 'Plot' menu
    MenuBuilder m_UnplotMenuBuilder; ///< Builder for the 'Unplot' menu
};

GenerateVariableMenuOperation::GenerateVariableMenuOperation(
    QMenu *menu, std::shared_ptr<Variable> variable,
    std::set<IVisualizationWidget *> variableContainers)
        : impl{spimpl::make_unique_impl<GenerateVariableMenuOperationPrivate>(
              menu, variable, std::move(variableContainers))}
{
}

void GenerateVariableMenuOperation::visitEnter(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to accommodate a variable
    Q_UNUSED(widget)

    // 'Plot' and 'Unplot' menus
    impl->visitRootEnter();
}

void GenerateVariableMenuOperation::visitLeave(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to accommodate a variable
    Q_UNUSED(widget)

    // 'Plot' and 'Unplot' menus
    impl->visitRootLeave();
}

void GenerateVariableMenuOperation::visitEnter(VisualizationTabWidget *tabWidget)
{
    if (tabWidget) {
        // 'Plot' and 'Unplot' menus
        impl->visitNodeEnter(*tabWidget);
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit enter VisualizationTabWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visitLeave(VisualizationTabWidget *tabWidget)
{
    if (tabWidget) {
        // 'Plot' menu
        impl->visitNodeLeavePlot(*tabWidget, QObject::tr("Open in a new zone"),
                                 [ varW = std::weak_ptr<Variable>{impl->m_Variable}, tabWidget ]() {
                                     if (auto var = varW.lock()) {
                                         tabWidget->createZone(var);
                                     }
                                 });

        // 'Unplot' menu
        impl->visitNodeLeaveUnplot();
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit leave VisualizationTabWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    if (zoneWidget) {
        // 'Plot' and 'Unplot' menus
        impl->visitNodeEnter(*zoneWidget);
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit enter VisualizationZoneWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visitLeave(VisualizationZoneWidget *zoneWidget)
{
    if (zoneWidget) {
        // 'Plot' menu
        impl->visitNodeLeavePlot(
            *zoneWidget, QObject::tr("Open in a new graph"),
            [ varW = std::weak_ptr<Variable>{impl->m_Variable}, zoneWidget ]() {
                if (auto var = varW.lock()) {
                    zoneWidget->createGraph(var);
                }
            });

        // 'Unplot' menu
        impl->visitNodeLeaveUnplot();
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit leave VisualizationZoneWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visit(VisualizationGraphWidget *graphWidget)
{
    if (graphWidget) {
        // 'Plot' menu
        impl->visitLeafPlot(*graphWidget, QObject::tr("Open in %1").arg(graphWidget->name()),
                            [ varW = std::weak_ptr<Variable>{impl->m_Variable}, graphWidget ]() {
                                if (auto var = varW.lock()) {
                                    graphWidget->addVariable(var, graphWidget->graphRange());
                                }
                            });

        // 'Unplot' menu
        impl->visitLeafUnplot(graphWidget, QObject::tr("Remove from %1").arg(graphWidget->name()),
                              [ varW = std::weak_ptr<Variable>{impl->m_Variable}, graphWidget ]() {
                                  if (auto var = varW.lock()) {
                                      graphWidget->removeVariable(var);
                                  }
                              });
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit VisualizationGraphWidget : the widget is null");
    }
}
