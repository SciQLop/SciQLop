#include "Visualization/operations/GenerateVariableMenuOperation.h"

#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"

#include <Variable/Variable.h>

#include <QMenu>
#include <QStack>

Q_LOGGING_CATEGORY(LOG_GenerateVariableMenuOperation, "GenerateVariableMenuOperation")

namespace {

/// Helper assigned to build the hierarchical menu associated with a variable
struct MenuBuilder {
    /**
     * Ctor
     * @param menu the parent menu
     */
    explicit MenuBuilder(QMenu *menu)
    {
        if (menu) {
            m_Menus.push(menu);
        }
        else {
            qCCritical(LOG_GenerateVariableMenuOperation())
                << QObject::tr("No parent menu has been defined");
        }
    }

    /**
     * Adds action to the current menu
     * @param actionName the name of the action
     * @param actionFunction the function that will be executed when the action is triggered
     */
    template <typename ActionFun>
    void addAction(const QString &actionName, ActionFun actionFunction)
    {
        if (auto currMenu = currentMenu()) {
            currMenu->addAction(actionName, actionFunction);
        }
        else {
            qCCritical(LOG_GenerateVariableMenuOperation())
                << QObject::tr("No current menu to attach the action");
        }
    }

    /**
     * Adds a new menu to the current menu
     * @param name the name of the menu
     */
    void addMenu(const QString &name)
    {
        if (auto currMenu = currentMenu()) {
            m_Menus.push(currMenu->addMenu(name));
        }
        else {
            qCCritical(LOG_GenerateVariableMenuOperation())
                << QObject::tr("No current menu to attach the new menu");
        }
    }

    /// Adds a separator to the current menu. The separator is added only if the menu already
    /// contains entries
    void addSeparator()
    {
        if (auto currMenu = currentMenu()) {
            if (!currMenu->isEmpty()) {
                currMenu->addSeparator();
            }
        }
        else {
            qCCritical(LOG_GenerateVariableMenuOperation())
                << QObject::tr("No current menu to attach the separator");
        }
    }

    /// Closes the current menu
    void closeMenu()
    {
        if (!m_Menus.isEmpty()) {
            if (auto closedMenu = m_Menus.pop()) {
                // Purge menu : if the closed menu has no entries, we remove it from its parent (the
                // current menu)
                if (auto currMenu = currentMenu()) {
                    if (closedMenu->isEmpty()) {
                        currMenu->removeAction(closedMenu->menuAction());
                    }
                }
            }
        }
    }

    /// Gets the current menu (i.e. the top menu of the stack)
    QMenu *currentMenu() const { return !m_Menus.isEmpty() ? m_Menus.top() : nullptr; }

    /// Stack of all menus currently opened
    QStack<QMenu *> m_Menus{};
};

} // namespace

struct GenerateVariableMenuOperation::GenerateVariableMenuOperationPrivate {
    explicit GenerateVariableMenuOperationPrivate(QMenu *menu, std::shared_ptr<Variable> variable)
            : m_Variable{variable}, m_MenuBuilder{menu}
    {
    }

    void visitNodeEnter(const IVisualizationWidget &container)
    {
        // Opens a new menu associated to the node
        m_MenuBuilder.addMenu(container.name());
    }

    template <typename ActionFun>
    void visitNodeLeave(const IVisualizationWidget &container, const QString &actionName,
                        ActionFun actionFunction)
    {
        if (m_Variable && container.canDrop(*m_Variable)) {
            m_MenuBuilder.addSeparator();
            m_MenuBuilder.addAction(actionName, actionFunction);
        }

        // Closes the menu associated to the node
        m_MenuBuilder.closeMenu();
    }

    template <typename ActionFun>
    void visitLeaf(const IVisualizationWidget &container, const QString &actionName,
                   ActionFun actionFunction)
    {
        if (m_Variable && container.canDrop(*m_Variable)) {
            m_MenuBuilder.addAction(actionName, actionFunction);
        }
    }

    std::shared_ptr<Variable> m_Variable;
    MenuBuilder m_MenuBuilder;
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
    if (tabWidget) {
        impl->visitNodeEnter(*tabWidget);
    }
}

void GenerateVariableMenuOperation::visitLeave(VisualizationTabWidget *tabWidget)
{
    if (tabWidget) {
        impl->visitNodeLeave(
            *tabWidget, QObject::tr("Open in a new zone"),
            [ var = impl->m_Variable, tabWidget ]() { tabWidget->createZone(var); });
    }
}

void GenerateVariableMenuOperation::visitEnter(VisualizationZoneWidget *zoneWidget)
{
    if (zoneWidget) {
        impl->visitNodeEnter(*zoneWidget);
    }
}

void GenerateVariableMenuOperation::visitLeave(VisualizationZoneWidget *zoneWidget)
{
    if (zoneWidget) {
        impl->visitNodeLeave(
            *zoneWidget, QObject::tr("Open in a new graph"),
            [ var = impl->m_Variable, zoneWidget ]() { zoneWidget->createGraph(var); });
    }
}

void GenerateVariableMenuOperation::visit(VisualizationGraphWidget *graphWidget)
{
    if (graphWidget) {
        impl->visitLeaf(
            *graphWidget, QObject::tr("Open in %1").arg(graphWidget->name()),
            [ var = impl->m_Variable, graphWidget ]() { graphWidget->addVariable(var); });
    }
}
