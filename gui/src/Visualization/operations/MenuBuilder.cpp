#include "Visualization/operations/MenuBuilder.h"

Q_LOGGING_CATEGORY(LOG_MenuBuilder, "MenuBuilder")

MenuBuilder::MenuBuilder(QMenu *menu)
{
    if (menu) {
        m_Menus.push(menu);
    }
    else {
        qCCritical(LOG_MenuBuilder()) << QObject::tr("No parent menu has been defined");
    }
}

QMenu *MenuBuilder::addMenu(const QString &name, const QIcon &icon)
{
    if (auto currMenu = currentMenu()) {
        auto menu = currMenu->addMenu(icon, name);
        m_Menus.push(menu);
        return menu;
    }
    else {
        qCCritical(LOG_MenuBuilder()) << QObject::tr("No current menu to attach the new menu");
        return nullptr;
    }
}

void MenuBuilder::addSeparator()
{
    if (auto currMenu = currentMenu()) {
        if (!currMenu->isEmpty()) {
            currMenu->addSeparator();
        }
    }
    else {
        qCCritical(LOG_MenuBuilder()) << QObject::tr("No current menu to attach the separator");
    }
}

void MenuBuilder::closeMenu()
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

QMenu *MenuBuilder::currentMenu() const
{
    return !m_Menus.isEmpty() ? m_Menus.top() : nullptr;
}
