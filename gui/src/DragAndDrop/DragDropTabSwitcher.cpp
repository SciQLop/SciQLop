#include "DragAndDrop/DragDropTabSwitcher.h"

#include <QAbstractButton>
#include <QDragEnterEvent>
#include <QDragMoveEvent>
#include <QTimer>

#include "SqpApplication.h"

Q_LOGGING_CATEGORY(LOG_DragDropTabSwitcher, "DragDropTabSwitcher")

const int CHANGE_TAB_INTERVAL = 400; // time necessary over a tab to accept the switch
const int SCROLL_BUTTON_AUTO_CLICK_INTERVAL
    = 500; // time between 2 auto clicks on a scroll button of the tab bar

struct DragDropTabSwitcher::DragDropTabSwitcherPrivate {

    QList<QTabBar *> m_TabBarList;
    QTabBar *m_CurrentTabBar = nullptr;

    int m_HoveredTabIndex = -1;
    std::unique_ptr<QTimer> m_TabSwitchTimer = nullptr;

    QAbstractButton *m_HoveredScrollButton = nullptr;
    std::unique_ptr<QTimer> m_ScrollButtonsTimer = nullptr;

    explicit DragDropTabSwitcherPrivate()
            : m_TabSwitchTimer{std::make_unique<QTimer>()},
              m_ScrollButtonsTimer{std::make_unique<QTimer>()}
    {
        m_TabSwitchTimer->setSingleShot(true);
        m_TabSwitchTimer->setInterval(CHANGE_TAB_INTERVAL);
        QObject::connect(m_TabSwitchTimer.get(), &QTimer::timeout, [this]() {
            if (m_CurrentTabBar) {
                m_CurrentTabBar->setCurrentIndex(m_HoveredTabIndex);
            }
            else {
                qCWarning(LOG_DragDropTabSwitcher()) << "DragDropTabSwitcherPrivate::timeout: "
                                                        "Cannot select a new tab: unknown current "
                                                        "tab bar.";
            }
        });

        m_ScrollButtonsTimer->setInterval(SCROLL_BUTTON_AUTO_CLICK_INTERVAL);
        QObject::connect(m_ScrollButtonsTimer.get(), &QTimer::timeout, [this]() {
            if (m_HoveredScrollButton) {
                m_HoveredScrollButton->animateClick();
            }
            else {
                qCWarning(LOG_DragDropTabSwitcher())
                    << "DragDropTabSwitcherPrivate::timeoutScroll: "
                       "Unknown scroll button";
            }
        });
    }

    bool isScrollTabButton(QAbstractButton *button, QTabBar *tabBar)
    {
        auto isNextOrPreviousTabButton = true;

        if (tabBar->isAncestorOf(button)) {
            for (auto i = 0; i < tabBar->count(); ++i) {
                if (tabBar->tabButton(i, QTabBar::RightSide) == button
                    || tabBar->tabButton(i, QTabBar::LeftSide) == button) {
                    isNextOrPreviousTabButton = false;
                    break;
                }
            }
        }
        else {
            isNextOrPreviousTabButton = false;
        }

        return isNextOrPreviousTabButton;
    }

    QAbstractButton *tabScrollButtonAt(const QPoint &pos, QTabBar *tabBar)
    {

        auto globalPos = tabBar->mapToGlobal(pos);

        auto widgetUnderMouse = sqpApp->widgetAt(globalPos);
        if (auto btn = qobject_cast<QAbstractButton *>(widgetUnderMouse)) {

            if (isScrollTabButton(btn, tabBar)) {
                return btn;
            }
        }

        return nullptr;
    }
};

DragDropTabSwitcher::DragDropTabSwitcher(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<DragDropTabSwitcherPrivate>()}
{
}

void DragDropTabSwitcher::addTabBar(QTabBar *tabBar)
{
    impl->m_TabBarList << tabBar;
    tabBar->setAcceptDrops(true);
}

void DragDropTabSwitcher::removeTabBar(QTabBar *tabBar)
{
    impl->m_TabBarList.removeAll(tabBar);
    tabBar->setAcceptDrops(false);
}

bool DragDropTabSwitcher::eventFilter(QObject *obj, QEvent *event)
{
    if (event->type() == QEvent::DragMove) {

        if (impl->m_CurrentTabBar) {

            QWidget *w = static_cast<QWidget *>(obj);
            if (!impl->m_CurrentTabBar->isAncestorOf(w)) {
                return false;
            }

            auto moveEvent = static_cast<QDragMoveEvent *>(event);

            auto scrollButton = impl->tabScrollButtonAt(moveEvent->pos(), impl->m_CurrentTabBar);

            if (!scrollButton) {

                auto tabIndex = impl->m_CurrentTabBar->tabAt(moveEvent->pos());
                if (tabIndex >= 0 && tabIndex != impl->m_CurrentTabBar->currentIndex()) {
                    // The mouse is over an unselected tab
                    if (!impl->m_TabSwitchTimer->isActive()
                        || tabIndex != impl->m_HoveredTabIndex) {
                        impl->m_HoveredTabIndex = tabIndex;
                        impl->m_TabSwitchTimer->start();
                    }
                    else {
                        // do nothing, timer already running
                    }
                }
                else {
                    impl->m_TabSwitchTimer->stop();
                }

                impl->m_ScrollButtonsTimer->stop();
            }
            else {
                // The mouse is over a scroll button
                // click it in a loop with a timer
                if (!impl->m_ScrollButtonsTimer->isActive()
                    || impl->m_HoveredScrollButton != scrollButton) {
                    impl->m_HoveredScrollButton = scrollButton;
                    impl->m_ScrollButtonsTimer->start();
                }
            }
        }
    }
    else if (event->type() == QEvent::DragEnter) {
        QWidget *w = static_cast<QWidget *>(obj);

        for (auto tabBar : impl->m_TabBarList) {
            if (w == tabBar) {
                auto enterEvent = static_cast<QDragEnterEvent *>(event);
                enterEvent->acceptProposedAction();
                enterEvent->setDropAction(Qt::IgnoreAction);
                impl->m_CurrentTabBar = tabBar;
                break;
            }
        }
    }
    else if (event->type() == QEvent::DragLeave || event->type() == QEvent::Drop) {
        if (impl->m_CurrentTabBar) {
            impl->m_HoveredTabIndex = -1;
            impl->m_TabSwitchTimer->stop();
            impl->m_CurrentTabBar = nullptr;
            impl->m_ScrollButtonsTimer->stop();
        }
    }

    return false;
}
