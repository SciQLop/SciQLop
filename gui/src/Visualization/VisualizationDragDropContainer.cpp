#include "Visualization/VisualizationDragDropContainer.h"
#include "DragDropHelper.h"
#include "SqpApplication.h"
#include "Visualization/VisualizationDragWidget.h"

#include "Common/VisualizationDef.h"

#include <QDrag>
#include <QDragEnterEvent>
#include <QVBoxLayout>

#include <cmath>
#include <memory>

Q_LOGGING_CATEGORY(LOG_VisualizationDragDropContainer, "VisualizationDragDropContainer")

struct VisualizationDragDropContainer::VisualizationDragDropContainerPrivate {

    QVBoxLayout *m_Layout;
    QStringList m_AcceptedMimeTypes;
    QStringList m_MergeAllowedMimeTypes;
    VisualizationDragDropContainer::AcceptMimeDataFunction m_AcceptMimeDataFun
        = [](auto mimeData) { return true; };
    int m_MinContainerHeight = 0;

    explicit VisualizationDragDropContainerPrivate(QWidget *widget)
    {
        m_Layout = new QVBoxLayout(widget);
        m_Layout->setContentsMargins(0, 0, 0, 0);
    }

    bool acceptMimeData(const QMimeData *data) const
    {
        for (const auto &type : m_AcceptedMimeTypes) {
            if (data->hasFormat(type) && m_AcceptMimeDataFun(data)) {
                return true;
            }
        }

        return false;
    }

    bool allowMergeMimeData(const QMimeData *data) const
    {
        for (const auto &type : m_MergeAllowedMimeTypes) {
            if (data->hasFormat(type)) {
                return true;
            }
        }

        return false;
    }

    bool hasPlaceHolder() const
    {
        return sqpApp->dragDropHelper().placeHolder().parentWidget() == m_Layout->parentWidget();
    }

    VisualizationDragWidget *getChildDragWidgetAt(const QWidget *parent, const QPoint &pos) const
    {
        VisualizationDragWidget *dragWidget = nullptr;

        for (auto child : parent->children()) {
            auto widget = qobject_cast<VisualizationDragWidget *>(child);
            if (widget && widget->isVisible()) {
                if (widget->frameGeometry().contains(pos)) {
                    dragWidget = widget;
                    break;
                }
            }
        }

        return dragWidget;
    }

    bool cursorIsInContainer(QWidget *container) const
    {
        auto adustNum = 18; // to be safe, in case of scrollbar on the side
        auto containerRect = QRect(QPoint(), container->contentsRect().size())
                                 .adjusted(adustNum, adustNum, -adustNum, -adustNum);
        return containerRect.contains(container->mapFromGlobal(QCursor::pos()));
    }

    int countDragWidget(const QWidget *parent) const
    {
        auto nbGraph = 0;
        for (auto child : parent->children()) {
            if (qobject_cast<VisualizationDragWidget *>(child)) {
                nbGraph += 1;
            }
        }

        return nbGraph;
    }

    void findPlaceHolderPosition(const QPoint &pos, bool canMerge,
                                 const VisualizationDragDropContainer *container);
};

VisualizationDragDropContainer::VisualizationDragDropContainer(QWidget *parent)
        : QWidget{parent},
          impl{spimpl::make_unique_impl<VisualizationDragDropContainerPrivate>(this)}
{
    setAcceptDrops(true);
}

void VisualizationDragDropContainer::addDragWidget(VisualizationDragWidget *dragWidget)
{
    impl->m_Layout->addWidget(dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this,
            &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::insertDragWidget(int index,
                                                      VisualizationDragWidget *dragWidget)
{
    impl->m_Layout->insertWidget(index, dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this,
            &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::setAcceptedMimeTypes(const QStringList &mimeTypes)
{
    impl->m_AcceptedMimeTypes = mimeTypes;
}

void VisualizationDragDropContainer::setMergeAllowedMimeTypes(const QStringList &mimeTypes)
{
    impl->m_MergeAllowedMimeTypes = mimeTypes;
}

int VisualizationDragDropContainer::countDragWidget() const
{
    return impl->countDragWidget(this);
}

void VisualizationDragDropContainer::setAcceptMimeDataFunction(
    VisualizationDragDropContainer::AcceptMimeDataFunction fun)
{
    impl->m_AcceptMimeDataFun = fun;
}

void VisualizationDragDropContainer::startDrag(VisualizationDragWidget *dragWidget,
                                               const QPoint &dragPosition)
{
    auto &helper = sqpApp->dragDropHelper();
    helper.resetDragAndDrop();

    // Note: The management of the drag object is done by Qt
    auto drag = new QDrag{dragWidget};
    drag->setHotSpot(dragPosition);

    auto mimeData = dragWidget->mimeData();
    drag->setMimeData(mimeData);

    auto pixmap = QPixmap(dragWidget->size());
    dragWidget->render(&pixmap);
    drag->setPixmap(pixmap);

    auto image = pixmap.toImage();
    mimeData->setImageData(image);
    mimeData->setUrls({helper.imageTemporaryUrl(image)});

    if (impl->m_Layout->indexOf(dragWidget) >= 0) {
        helper.setCurrentDragWidget(dragWidget);

        if (impl->cursorIsInContainer(this)) {
            auto dragWidgetIndex = impl->m_Layout->indexOf(dragWidget);
            helper.insertPlaceHolder(impl->m_Layout, dragWidgetIndex);
            dragWidget->setVisible(false);
        }

        // Note: The exec() is blocking on windows but not on linux and macOS
        drag->exec(Qt::MoveAction | Qt::CopyAction);
    }
    else {
        qCWarning(LOG_VisualizationDragDropContainer())
            << tr("VisualizationDragDropContainer::startDrag, drag aborted, the specified "
                  "VisualizationDragWidget is not found in this container.");
    }
}

void VisualizationDragDropContainer::dragEnterEvent(QDragEnterEvent *event)
{
    if (impl->acceptMimeData(event->mimeData())) {
        event->acceptProposedAction();

        auto &helper = sqpApp->dragDropHelper();

        if (!impl->hasPlaceHolder()) {
            auto dragWidget = helper.getCurrentDragWidget();

            if (dragWidget) {
                // If the drag&drop is internal to the visualization, entering the container hide
                // the dragWidget which was made visible by the dragLeaveEvent
                auto parentWidget
                    = qobject_cast<VisualizationDragDropContainer *>(dragWidget->parentWidget());
                if (parentWidget) {
                    dragWidget->setVisible(false);
                }
            }

            auto canMerge = impl->allowMergeMimeData(event->mimeData());
            impl->findPlaceHolderPosition(event->pos(), canMerge, this);
        }
        else {
            // do nothing
        }
    }
    else {
        event->ignore();
    }

    QWidget::dragEnterEvent(event);
}

void VisualizationDragDropContainer::dragLeaveEvent(QDragLeaveEvent *event)
{
    Q_UNUSED(event);

    auto &helper = sqpApp->dragDropHelper();

    if (!impl->cursorIsInContainer(this)) {
        helper.removePlaceHolder();
        helper.setHightlightedDragWidget(nullptr);
        impl->m_MinContainerHeight = 0;

        auto dragWidget = helper.getCurrentDragWidget();
        if (dragWidget) {
            // dragWidget has a value only if the drag is started from the visualization
            // In that case, shows the drag widget at its original place
            // So the drag widget doesn't stay hidden if the drop occurs outside the visualization
            // drop zone (It is not possible to catch a drop event outside of the application)

            if (dragWidget) {
                dragWidget->setVisible(true);
            }
        }
    }
    else {
        // Leave event probably received for a child widget.
        // Do nothing.
        // Note: The DragLeave event, doesn't have any mean to determine who sent it.
    }

    QWidget::dragLeaveEvent(event);
}

void VisualizationDragDropContainer::dragMoveEvent(QDragMoveEvent *event)
{
    if (impl->acceptMimeData(event->mimeData())) {
        auto canMerge = impl->allowMergeMimeData(event->mimeData());
        impl->findPlaceHolderPosition(event->pos(), canMerge, this);
    }
    else {
        event->ignore();
    }

    QWidget::dragMoveEvent(event);
}

void VisualizationDragDropContainer::dropEvent(QDropEvent *event)
{
    if (impl->acceptMimeData(event->mimeData())) {
        auto dragWidget = sqpApp->dragDropHelper().getCurrentDragWidget();
        if (impl->hasPlaceHolder()) {
            auto &helper = sqpApp->dragDropHelper();

            auto droppedIndex = impl->m_Layout->indexOf(&helper.placeHolder());

            if (dragWidget) {
                auto dragWidgetIndex = impl->m_Layout->indexOf(dragWidget);
                if (dragWidgetIndex >= 0 && dragWidgetIndex < droppedIndex) {
                    // Correction of the index if the drop occurs in the same container
                    // and if the drag is started from the visualization (in that case, the
                    // dragWidget is hidden)
                    droppedIndex -= 1;
                }

                dragWidget->setVisible(true);
            }

            event->acceptProposedAction();

            helper.removePlaceHolder();

            emit dropOccured(droppedIndex, event->mimeData());
        }
        else {
            qCWarning(LOG_VisualizationDragDropContainer())
                << tr("VisualizationDragDropContainer::dropEvent, couldn't drop because the "
                      "placeHolder is not found.");
            // Q_ASSERT(false);
        }
    }
    else {
        event->ignore();
    }

    sqpApp->dragDropHelper().setHightlightedDragWidget(nullptr);
    impl->m_MinContainerHeight = 0;

    QWidget::dropEvent(event);
}


void VisualizationDragDropContainer::VisualizationDragDropContainerPrivate::findPlaceHolderPosition(
    const QPoint &pos, bool canMerge, const VisualizationDragDropContainer *container)
{
    auto &helper = sqpApp->dragDropHelper();

    auto dragWidgetHovered = getChildDragWidgetAt(container, pos);
    if (dragWidgetHovered) {
        auto nbDragWidget = countDragWidget(container);
        if (nbDragWidget > 0) {

            if (m_MinContainerHeight == 0) {
                m_MinContainerHeight = container->size().height();
            }

            m_MinContainerHeight = qMin(m_MinContainerHeight, container->size().height());
            auto graphHeight = qMax(m_MinContainerHeight / nbDragWidget, GRAPH_MINIMUM_HEIGHT);

            auto posY = pos.y();
            auto dropIndex = floor(posY / graphHeight);
            auto zoneSize = qMin(graphHeight / 4.0, 75.0);


            auto isOnTop = posY < dropIndex * graphHeight + zoneSize;
            auto isOnBottom = posY > (dropIndex + 1) * graphHeight - zoneSize;

            auto placeHolderIndex = m_Layout->indexOf(&(helper.placeHolder()));

            if (isOnTop || isOnBottom || !canMerge) {
                if (isOnBottom) {
                    dropIndex += 1;
                }

                if (helper.getCurrentDragWidget()) {
                    auto dragWidgetIndex = m_Layout->indexOf(helper.getCurrentDragWidget());
                    if (dragWidgetIndex >= 0 && dragWidgetIndex <= dropIndex) {
                        // Correction of the index if the drop occurs in the same container
                        // and if the drag is started from the visualization (in that case, the
                        // dragWidget is hidden)
                        dropIndex += 1;
                    }
                }

                if (dropIndex != placeHolderIndex) {
                    helper.insertPlaceHolder(m_Layout, dropIndex);
                }

                helper.setHightlightedDragWidget(nullptr);
            }
            else if (canMerge) {
                // drop on the middle -> merge
                if (hasPlaceHolder()) {
                    helper.removePlaceHolder();
                }

                helper.setHightlightedDragWidget(dragWidgetHovered);
            }
        }
        else {
            qCWarning(LOG_VisualizationDragDropContainer())
                << tr("VisualizationDragDropContainer::dragMoveEvent, no widget found in the "
                      "container");
        }
    }
    else if (!hasPlaceHolder()) {
        // Drop on an empty container, just add the placeHolder at the top
        helper.insertPlaceHolder(m_Layout, 0);
    }
    else {
        // No hovered drag widget, the mouse is probably hover the placeHolder
        // Do nothing
    }
}
