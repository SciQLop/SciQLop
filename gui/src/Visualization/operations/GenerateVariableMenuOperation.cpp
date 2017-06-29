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
    explicit GenerateVariableMenuOperationPrivate(QMenu *menu, std::shared_ptr<Variable> variable)
            : m_Variable{variable}, m_PlotMenuBuilder{menu}
    {
    }

    void visitRootEnter()
    {
        // Creates the root menu
        m_PlotMenuBuilder.addMenu(QObject::tr("Plot"), QIcon{":/icones/plot.png"});
    }

    void visitRootLeave()
    {
        // Closes the root menu
        m_PlotMenuBuilder.closeMenu();
    }

    void visitNodeEnter(const IVisualizationWidget &container)
    {
        // Opens a new menu associated to the node
        m_PlotMenuBuilder.addMenu(container.name());
    }

    template <typename ActionFun>
    void visitNodeLeave(const IVisualizationWidget &container, const QString &actionName,
                        ActionFun actionFunction)
    {
        if (m_Variable && container.canDrop(*m_Variable)) {
            m_PlotMenuBuilder.addSeparator();
            m_PlotMenuBuilder.addAction(actionName, actionFunction);
        }

        // Closes the menu associated to the node
        m_PlotMenuBuilder.closeMenu();
    }

    template <typename ActionFun>
    void visitLeaf(const IVisualizationWidget &container, const QString &actionName,
                   ActionFun actionFunction)
    {
        if (m_Variable && container.canDrop(*m_Variable)) {
            m_PlotMenuBuilder.addAction(actionName, actionFunction);
        }
    }

    std::shared_ptr<Variable> m_Variable;
    MenuBuilder m_PlotMenuBuilder; ///< Builder for the 'Plot' menu
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

    impl->visitRootEnter();
}

void GenerateVariableMenuOperation::visitLeave(VisualizationWidget *widget)
{
    // VisualizationWidget is not intended to accommodate a variable
    Q_UNUSED(widget)

    impl->visitRootLeave();
}

void GenerateVariableMenuOperation::visitEnter(VisualizationTabWidget *tabWidget)
{
    if (tabWidget) {
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
        impl->visitNodeLeave(
            *tabWidget, QObject::tr("Open in a new zone"),
            [ var = impl->m_Variable, tabWidget ]() { tabWidget->createZone(var); });
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit leave VisualizationTabWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    if (zoneWidget) {
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
        impl->visitNodeLeave(
            *zoneWidget, QObject::tr("Open in a new graph"),
            [ var = impl->m_Variable, zoneWidget ]() { zoneWidget->createGraph(var); });
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit leave VisualizationZoneWidget : the widget is null");
    }
}

void GenerateVariableMenuOperation::visit(VisualizationGraphWidget *graphWidget)
{
    if (graphWidget) {
        impl->visitLeaf(
            *graphWidget, QObject::tr("Open in %1").arg(graphWidget->name()),
            [ var = impl->m_Variable, graphWidget ]() { graphWidget->addVariableUsingGraph(var); });
    }
    else {
        qCCritical(LOG_GenerateVariableMenuOperation(),
                   "Can't visit VisualizationGraphWidget : the widget is null");
    }
}
