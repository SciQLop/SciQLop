#include "DragDropHelper.h"
#include "Visualization/VisualizationDragWidget.h"
#include "SqpApplication.h"

#include <QDragMoveEvent>
#include <QDragEnterEvent>
#include <QScrollBar>
#include <QScrollArea>
#include <QVBoxLayout>
#include <QTimer>
#include <QDir>

const QString DragDropHelper::MIME_TYPE_GRAPH = "scqlop/graph";
const QString DragDropHelper::MIME_TYPE_ZONE = "scqlop/zone";

const int SCROLL_SPEED = 5;
const int SCROLL_ZONE_SIZE = 50;

struct DragDropScroller::DragDropScrollerPrivate {

    QList<QScrollArea*> m_scrollAreas;
    QScrollArea* m_currentScrollArea = nullptr;
    std::unique_ptr<QTimer> m_timer = nullptr;


    enum class ScrollDirection {up, down, unknown};
    ScrollDirection m_direction = ScrollDirection::unknown;

    explicit DragDropScrollerPrivate()
        : m_timer{std::make_unique<QTimer>()}
    {
        m_timer->setInterval(0);
    }
};

DragDropScroller::DragDropScroller(QObject* parent)
    : QObject{parent},  impl{spimpl::make_unique_impl<DragDropScrollerPrivate>()}
{
    connect(impl->m_timer.get(), &QTimer::timeout, this, &DragDropScroller::onTimer);
}

void DragDropScroller::addScrollArea(QScrollArea* scrollArea)
{
    impl->m_scrollAreas << scrollArea;
    scrollArea->viewport()->setAcceptDrops(true);
}

void DragDropScroller::removeScrollArea(QScrollArea* scrollArea)
{
    impl->m_scrollAreas.removeAll(scrollArea);
    scrollArea->viewport()->setAcceptDrops(false);
}

bool DragDropScroller::eventFilter(QObject *obj, QEvent *event)
{
    if (event->type() == QEvent::DragMove)
    {
        auto w = static_cast<QWidget*>(obj);

        if (impl->m_currentScrollArea && impl->m_currentScrollArea->isAncestorOf(w))
        {
            auto moveEvent = static_cast<QDragMoveEvent*>(event);

            auto pos = moveEvent->pos();
            if (impl->m_currentScrollArea->viewport() != w)
            {
                auto globalPos = w->mapToGlobal(moveEvent->pos());
                pos = impl->m_currentScrollArea->viewport()->mapFromGlobal(globalPos);
            }

            auto isInTopZone = pos.y() > impl->m_currentScrollArea->viewport()->size().height() - SCROLL_ZONE_SIZE;
            auto isInBottomZone = pos.y() < SCROLL_ZONE_SIZE;

            if (!isInTopZone && !isInBottomZone)
            {
                impl->m_direction = DragDropScrollerPrivate::ScrollDirection::unknown;
                impl->m_timer->stop();
            }
            else if (!impl->m_timer->isActive())
            {
                impl->m_direction = isInTopZone ? DragDropScrollerPrivate::ScrollDirection::up : DragDropScrollerPrivate::ScrollDirection::down;
                impl->m_timer->start();
            }
        }
    }
    else if (event->type() == QEvent::DragEnter)
    {
        auto w = static_cast<QWidget*>(obj);

        for (auto scrollArea : impl-> m_scrollAreas)
        {
            if (impl->m_currentScrollArea != scrollArea && scrollArea->isAncestorOf(w))
            {
                auto enterEvent = static_cast<QDragEnterEvent*>(event);
                enterEvent->acceptProposedAction();
                enterEvent->setDropAction(Qt::IgnoreAction);
                impl->m_currentScrollArea = scrollArea;
                break;
            }
        }
    }
    else if (event->type() == QEvent::DragLeave)
    {
        auto w = static_cast<QWidget*>(obj);
        if (impl->m_currentScrollArea)
        {
            if (!QRect(QPoint(), impl->m_currentScrollArea->size()).contains(impl->m_currentScrollArea->mapFromGlobal(QCursor::pos())))
            {
                impl->m_currentScrollArea = nullptr;
                impl->m_direction = DragDropScrollerPrivate::ScrollDirection::unknown;
                impl->m_timer->stop();
            }
        }
    }
    else if (event->type() == QEvent::Drop)
    {
        auto w = static_cast<QWidget*>(obj);
        if (impl->m_currentScrollArea)
        {
            impl->m_currentScrollArea = nullptr;
            impl->m_direction = DragDropScrollerPrivate::ScrollDirection::unknown;
            impl->m_timer->stop();
        }
    }

    return false;
}

void DragDropScroller::onTimer()
{
    if (impl->m_currentScrollArea)
    {
        auto mvt = 0;
        switch (impl->m_direction)
        {
        case DragDropScrollerPrivate::ScrollDirection::up:
            mvt = SCROLL_SPEED;
            break;
        case DragDropScrollerPrivate::ScrollDirection::down:
            mvt = -SCROLL_SPEED;
            break;
        default:
            break;
        }

        impl->m_currentScrollArea->verticalScrollBar()->setValue(impl->m_currentScrollArea->verticalScrollBar()->value() + mvt);
    }
}

struct DragDropHelper::DragDropHelperPrivate {

    VisualizationDragWidget* m_currentDragWidget = nullptr;
    std::unique_ptr<QWidget> m_placeHolder = nullptr;
    std::unique_ptr<DragDropScroller> m_dragDropScroller = nullptr;
    QString m_imageTempUrl; //Temporary file for image url generated by the drag & drop. Not using QTemporaryFile to have a name which is not generated.

    explicit DragDropHelperPrivate()
        : m_placeHolder{std::make_unique<QWidget>()},
          m_dragDropScroller{std::make_unique<DragDropScroller>()}
    {
         m_placeHolder->setStyleSheet("background-color: #BBD5EE; border:2px solid #2A7FD4");
         sqpApp->installEventFilter(m_dragDropScroller.get());


         m_imageTempUrl = QDir::temp().absoluteFilePath("Scqlop_graph.png");
    }

    void preparePlaceHolder() const
    {
        if (m_currentDragWidget)
        {
            m_placeHolder->setMinimumSize(m_currentDragWidget->size());
            m_placeHolder->setSizePolicy(m_currentDragWidget->sizePolicy());
        }
        else
        {
            m_placeHolder->setMinimumSize(200, 200);
        }
    }
};


DragDropHelper::DragDropHelper() :
    impl{spimpl::make_unique_impl<DragDropHelperPrivate>()}
{
}

DragDropHelper::~DragDropHelper()
{
    QFile::remove(impl->m_imageTempUrl);
}

void DragDropHelper::setCurrentDragWidget(VisualizationDragWidget *dragWidget)
{
    impl->m_currentDragWidget = dragWidget;
}

VisualizationDragWidget *DragDropHelper::getCurrentDragWidget() const
{
    return impl->m_currentDragWidget;
}


QWidget& DragDropHelper::placeHolder() const
{
    return *impl->m_placeHolder;
}

void DragDropHelper::insertPlaceHolder(QVBoxLayout *layout, int index)
{
    removePlaceHolder();
    impl->preparePlaceHolder();
    layout->insertWidget(index, impl->m_placeHolder.get());
    impl->m_placeHolder->show();
}

void DragDropHelper::removePlaceHolder()
{
    auto parentWidget = impl->m_placeHolder->parentWidget();
    if (parentWidget)
    {
        parentWidget->layout()->removeWidget(impl->m_placeHolder.get());
        impl->m_placeHolder->setParent(nullptr);
        impl->m_placeHolder->hide();
    }
}

bool DragDropHelper::isPlaceHolderSet() const
{
    return impl->m_placeHolder->parentWidget();
}

void DragDropHelper::addDragDropScrollArea(QScrollArea *scrollArea)
{
   impl->m_dragDropScroller->addScrollArea(scrollArea);
}

void DragDropHelper::removeDragDropScrollArea(QScrollArea *scrollArea)
{
    impl->m_dragDropScroller->removeScrollArea(scrollArea);
}

QUrl DragDropHelper::imageTemporaryUrl(const QImage& image) const
{
    image.save(impl->m_imageTempUrl);
    return QUrl::fromLocalFile(impl->m_imageTempUrl);
}

