#include "DragAndDrop/DragDropScroller.h"

#include <QDragEnterEvent>
#include <QDragMoveEvent>
#include <QScrollBar>
#include <QTimer>

const int SCROLL_SPEED = 5;
const int SCROLL_ZONE_SIZE = 50;

struct DragDropScroller::DragDropScrollerPrivate {

    QList<QScrollArea *> m_ScrollAreas;
    QScrollArea *m_CurrentScrollArea = nullptr;
    std::unique_ptr<QTimer> m_Timer = nullptr;

    enum class ScrollDirection { up, down, unknown };
    ScrollDirection m_Direction = ScrollDirection::unknown;

    explicit DragDropScrollerPrivate() : m_Timer{std::make_unique<QTimer>()}
    {
        m_Timer->setInterval(0);
    }
};

DragDropScroller::DragDropScroller(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<DragDropScrollerPrivate>()}
{
    connect(impl->m_Timer.get(), &QTimer::timeout, this, &DragDropScroller::onTimer);
}

void DragDropScroller::addScrollArea(QScrollArea *scrollArea)
{
    impl->m_ScrollAreas << scrollArea;
    scrollArea->viewport()->setAcceptDrops(true);
}

void DragDropScroller::removeScrollArea(QScrollArea *scrollArea)
{
    impl->m_ScrollAreas.removeAll(scrollArea);
    scrollArea->viewport()->setAcceptDrops(false);
}

bool DragDropScroller::eventFilter(QObject *obj, QEvent *event)
{
    if (event->type() == QEvent::DragMove) {
        auto w = static_cast<QWidget *>(obj);

        if (impl->m_CurrentScrollArea && impl->m_CurrentScrollArea->isAncestorOf(w)) {
            auto moveEvent = static_cast<QDragMoveEvent *>(event);

            auto pos = moveEvent->pos();
            if (impl->m_CurrentScrollArea->viewport() != w) {
                auto globalPos = w->mapToGlobal(moveEvent->pos());
                pos = impl->m_CurrentScrollArea->viewport()->mapFromGlobal(globalPos);
            }

            auto isInTopZone = pos.y() > impl->m_CurrentScrollArea->viewport()->size().height()
                                             - SCROLL_ZONE_SIZE;
            auto isInBottomZone = pos.y() < SCROLL_ZONE_SIZE;

            if (!isInTopZone && !isInBottomZone) {
                impl->m_Direction = DragDropScrollerPrivate::ScrollDirection::unknown;
                impl->m_Timer->stop();
            }
            else if (!impl->m_Timer->isActive()) {
                impl->m_Direction = isInTopZone ? DragDropScrollerPrivate::ScrollDirection::up
                                                : DragDropScrollerPrivate::ScrollDirection::down;
                impl->m_Timer->start();
            }
        }
    }
    else if (event->type() == QEvent::DragEnter) {
        auto w = static_cast<QWidget *>(obj);

        for (auto scrollArea : impl->m_ScrollAreas) {
            if (impl->m_CurrentScrollArea != scrollArea && scrollArea->isAncestorOf(w)) {
                auto enterEvent = static_cast<QDragEnterEvent *>(event);
                enterEvent->acceptProposedAction();
                enterEvent->setDropAction(Qt::IgnoreAction);
                impl->m_CurrentScrollArea = scrollArea;
                break;
            }
        }
    }
    else if (event->type() == QEvent::DragLeave) {
        if (impl->m_CurrentScrollArea) {
            if (!QRect(QPoint(), impl->m_CurrentScrollArea->size())
                     .contains(impl->m_CurrentScrollArea->mapFromGlobal(QCursor::pos()))) {
                impl->m_CurrentScrollArea = nullptr;
                impl->m_Direction = DragDropScrollerPrivate::ScrollDirection::unknown;
                impl->m_Timer->stop();
            }
        }
    }
    else if (event->type() == QEvent::Drop) {
        if (impl->m_CurrentScrollArea) {
            impl->m_CurrentScrollArea = nullptr;
            impl->m_Direction = DragDropScrollerPrivate::ScrollDirection::unknown;
            impl->m_Timer->stop();
        }
    }

    return false;
}

void DragDropScroller::onTimer()
{
    if (impl->m_CurrentScrollArea) {
        auto mvt = 0;
        switch (impl->m_Direction) {
            case DragDropScrollerPrivate::ScrollDirection::up:
                mvt = SCROLL_SPEED;
                break;
            case DragDropScrollerPrivate::ScrollDirection::down:
                mvt = -SCROLL_SPEED;
                break;
            default:
                break;
        }

        impl->m_CurrentScrollArea->verticalScrollBar()->setValue(
            impl->m_CurrentScrollArea->verticalScrollBar()->value() + mvt);
    }
}
