#ifndef SCIQLOP_MENUBUILDER_H
#define SCIQLOP_MENUBUILDER_H

#include <QLoggingCategory>
#include <QMenu>
#include <QStack>

Q_DECLARE_LOGGING_CATEGORY(LOG_MenuBuilder)

/// Helper assigned to build a hierarchical menu
class MenuBuilder {
public:
    /**
     * Ctor
     * @param menu the parent menu
     */
    explicit MenuBuilder(QMenu *menu);

    /**
     * Adds action to the current menu
     * @param actionName the name of the action
     * @param actionFunction the function that will be executed when the action is triggered
     */
    template <typename ActionFun>
    void addAction(const QString &actionName, ActionFun actionFunction);

    /**
     * Adds a new menu to the current menu
     * @param name the name of the menu
     * @param icon the icon of the menu (can be null)
     */
    void addMenu(const QString &name, const QIcon &icon = {});

    /// Adds a separator to the current menu. The separator is added only if the menu already
    /// contains entries
    void addSeparator();

    /// Closes the current menu
    void closeMenu();

private:
    /// @return the current menu (i.e. the top menu of the stack), nullptr if there is no menu
    QMenu *currentMenu() const;

    /// Stack of all menus currently opened
    QStack<QMenu *> m_Menus{};
};

template <typename ActionFun>
void MenuBuilder::addAction(const QString &actionName, ActionFun actionFunction)
{
    if (auto currMenu = currentMenu()) {
        currMenu->addAction(actionName, actionFunction);
    }
    else {
        qCCritical(LOG_MenuBuilder()) << QObject::tr("No current menu to attach the action");
    }
}

#endif // SCIQLOP_MENUBUILDER_H
