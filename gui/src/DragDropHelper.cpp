#include "DragDropHelper.h"
#include "SqpApplication.h"
#include "Visualization/VisualizationDragDropContainer.h"
#include "Visualization/VisualizationDragWidget.h"
#include "Visualization/VisualizationWidget.h"
#include "Visualization/operations/FindVariableOperation.h"

#include "Variable/VariableController.h"

#include "Common/MimeTypesDef.h"
#include "Common/VisualizationDef.h"

#include <QDir>
#include <QDragEnterEvent>
#include <QDragMoveEvent>
#include <QScrollArea>
#include <QScrollBar>
#include <QTimer>
#include <QVBoxLayout>

const int SCROLL_SPEED = 5;
const int SCROLL_ZONE_SIZE = 50;

Q_LOGGING_CATEGORY(LOG_DragDropHelper, "DragDrophelper")

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

struct DragDropHelper::DragDropHelperPrivate {

    VisualizationDragWidget *m_CurrentDragWidget = nullptr;
    std::unique_ptr<QWidget> m_PlaceHolder = nullptr;
    std::unique_ptr<DragDropScroller> m_DragDropScroller = nullptr;
    QString m_ImageTempUrl; // Temporary file for image url generated by the drag & drop. Not using
                            // QTemporaryFile to have a name which is not generated.

    explicit DragDropHelperPrivate()
            : m_PlaceHolder{std::make_unique<QWidget>()},
              m_DragDropScroller{std::make_unique<DragDropScroller>()}
    {
        m_PlaceHolder->setStyleSheet("background-color: #BBD5EE; border:2px solid #2A7FD4");
        sqpApp->installEventFilter(m_DragDropScroller.get());


        m_ImageTempUrl = QDir::temp().absoluteFilePath("Scqlop_graph.png");
    }

    void preparePlaceHolder() const
    {
        if (m_CurrentDragWidget) {
            m_PlaceHolder->setMinimumSize(m_CurrentDragWidget->size());
            m_PlaceHolder->setSizePolicy(m_CurrentDragWidget->sizePolicy());
        }
        else {
            // Configuration of the placeHolder when there is no dragWidget
            // (for instance with a drag from a variable)

            m_PlaceHolder->setMinimumSize(0, GRAPH_MINIMUM_HEIGHT);
            m_PlaceHolder->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
        }
    }
};


DragDropHelper::DragDropHelper() : impl{spimpl::make_unique_impl<DragDropHelperPrivate>()}
{
}

DragDropHelper::~DragDropHelper()
{
    QFile::remove(impl->m_ImageTempUrl);
}

void DragDropHelper::resetDragAndDrop()
{
    setCurrentDragWidget(nullptr);
}

void DragDropHelper::setCurrentDragWidget(VisualizationDragWidget *dragWidget)
{
    impl->m_CurrentDragWidget = dragWidget;
}

VisualizationDragWidget *DragDropHelper::getCurrentDragWidget() const
{
    return impl->m_CurrentDragWidget;
}


QWidget &DragDropHelper::placeHolder() const
{
    return *impl->m_PlaceHolder;
}

void DragDropHelper::insertPlaceHolder(QVBoxLayout *layout, int index)
{
    removePlaceHolder();
    impl->preparePlaceHolder();
    layout->insertWidget(index, impl->m_PlaceHolder.get());
    impl->m_PlaceHolder->show();
}

void DragDropHelper::removePlaceHolder()
{
    auto parentWidget = impl->m_PlaceHolder->parentWidget();
    if (parentWidget) {
        parentWidget->layout()->removeWidget(impl->m_PlaceHolder.get());
        impl->m_PlaceHolder->setParent(nullptr);
        impl->m_PlaceHolder->hide();
    }
}

bool DragDropHelper::isPlaceHolderSet() const
{
    return impl->m_PlaceHolder->parentWidget();
}

void DragDropHelper::addDragDropScrollArea(QScrollArea *scrollArea)
{
    impl->m_DragDropScroller->addScrollArea(scrollArea);
}

void DragDropHelper::removeDragDropScrollArea(QScrollArea *scrollArea)
{
    impl->m_DragDropScroller->removeScrollArea(scrollArea);
}

QUrl DragDropHelper::imageTemporaryUrl(const QImage &image) const
{
    image.save(impl->m_ImageTempUrl);
    return QUrl::fromLocalFile(impl->m_ImageTempUrl);
}

bool DragDropHelper::checkMimeDataForVisualization(const QMimeData *mimeData,
                                                   VisualizationDragDropContainer *dropContainer)
{
    if (!mimeData || !dropContainer) {
        qCWarning(LOG_DragDropHelper()) << QObject::tr(
            "DragDropHelper::checkMimeDataForVisualization, invalid input parameters.");
        Q_ASSERT(false);
    }

    auto result = true;

    if (mimeData->hasFormat(MIME_TYPE_VARIABLE_LIST)) {
        auto variables = sqpApp->variableController().variablesForMimeData(
            mimeData->data(MIME_TYPE_VARIABLE_LIST));

        if (variables.count() == 1) {
            // Check that the viariable is not already in a graph

            // Search for the top level VisualizationWidget
            auto parent = dropContainer->parentWidget();
            while (parent && qobject_cast<VisualizationWidget *>(parent) == nullptr) {
                parent = parent->parentWidget();
            }

            if (parent) {
                auto visualizationWidget = static_cast<VisualizationWidget *>(parent);

                FindVariableOperation findVariableOperation{variables.first()};
                visualizationWidget->accept(&findVariableOperation);
                auto variableContainers = findVariableOperation.result();
                if (!variableContainers.empty()) {
                    result = false;
                }
            }
            else {
                qCWarning(LOG_DragDropHelper()) << QObject::tr(
                    "DragDropHelper::checkMimeDataForVisualization, the parent "
                    "VisualizationWidget cannot be found.");
                result = false;
            }
        }
        else {
            result = false;
        }
    }

    return result;
}
