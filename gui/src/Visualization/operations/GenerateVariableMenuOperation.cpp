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

    /// Closes the current menu
    void closeMenu()
    {
        if (!m_Menus.isEmpty()) {
            m_Menus.pop();
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
    void visitNodeLeave()
    {
        // Closes the menu associated to the node
        m_MenuBuilder.closeMenu();
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
        impl->visitNodeLeave();
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
        impl->visitNodeLeave();
    }
}

void GenerateVariableMenuOperation::visit(VisualizationGraphWidget *graphWidget)
{
    /// @todo ALX
}
