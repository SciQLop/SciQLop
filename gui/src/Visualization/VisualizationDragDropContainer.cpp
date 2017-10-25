#include "Visualization/VisualizationDragDropContainer.h"
#include "Visualization/VisualizationDragWidget.h"
#include "SqpApplication.h"
#include "DragDropHelper.h"

#include <QDrag>
#include <QVBoxLayout>
#include <QDragEnterEvent>

#include <memory>

struct VisualizationDragDropContainer::VisualizationDragDropContainerPrivate {

    QVBoxLayout* m_layout;
    QStringList m_acceptedMimeTypes;
    QStringList m_mergeAllowedMimeTypes;

    explicit VisualizationDragDropContainerPrivate(QWidget* widget)
    {
        m_layout  = new QVBoxLayout(widget);
        m_layout->setContentsMargins(0,0,0,0);
    }

    bool acceptMimeData(const QMimeData* data) const
    {
        for (const auto& type : m_acceptedMimeTypes)
        {
            if (data->hasFormat(type))
                return true;
        }

        return false;
    }

    bool allowMergeMimeData(const QMimeData* data) const
    {
        for (const auto& type : m_mergeAllowedMimeTypes)
        {
            if (data->hasFormat(type))
                return true;
        }

        return false;
    }

    bool hasPlaceHolder() const
    {
        return sqpApp->dragDropHelper().placeHolder().parentWidget() == m_layout->parentWidget();
    }

    VisualizationDragWidget* getChildDragWidgetAt(QWidget* parent, const QPoint &pos) const
    {
        VisualizationDragWidget* dragWidget = nullptr;

        for (auto child : parent->children())
        {
            auto widget = qobject_cast<VisualizationDragWidget*>(child);
            if (widget && widget->isVisible())
            {
                if (widget->frameGeometry().contains(pos))
                {
                    dragWidget = widget;
                    break;
                }
            }
        }

        return dragWidget;
    }

    bool cursorIsInContainer(QWidget* container) const
    {
        auto adustNum = 18; //to be safe, in case of scrollbar on the side
        auto containerRect = QRect(QPoint(), container->contentsRect().size()).adjusted(adustNum, adustNum, -adustNum, -adustNum);
        qDebug() << containerRect << container->mapFromGlobal(QCursor::pos());
        return containerRect.contains(container->mapFromGlobal(QCursor::pos()));
    }

};

VisualizationDragDropContainer::VisualizationDragDropContainer(QWidget *parent)
    : QWidget{parent}, impl{spimpl::make_unique_impl<VisualizationDragDropContainerPrivate>(this)}
{
    setAcceptDrops(true);
}

void VisualizationDragDropContainer::addDragWidget(VisualizationDragWidget *dragWidget)
{
    impl->m_layout->addWidget(dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this, &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::insertDragWidget(int index, VisualizationDragWidget *dragWidget)
{
    impl->m_layout->insertWidget(index, dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this, &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::setAcceptedMimeTypes(const QStringList &mimeTypes)
{
    impl->m_acceptedMimeTypes = mimeTypes;
}

void VisualizationDragDropContainer::setMergeAllowedMimeTypes(const QStringList &mimeTypes)
{
    impl->m_mergeAllowedMimeTypes = mimeTypes;
}

int VisualizationDragDropContainer::countDragWidget() const
{
    auto nbGraph = 0;
    for (auto child : children())
    {
        auto widget = qobject_cast<VisualizationDragWidget*>(child);
        if (widget)
        {
            nbGraph += 1;
        }
    }

    return nbGraph;
}

void VisualizationDragDropContainer::startDrag(VisualizationDragWidget *dragWidget, const QPoint &dragPosition)
{
    auto& helper = sqpApp->dragDropHelper();

    //Note: The management of the drag object is done by Qt
    auto *drag = new QDrag{dragWidget};
    drag->setHotSpot(dragPosition);

    auto mimeData = dragWidget->mimeData();
    drag->setMimeData(mimeData);

    auto pixmap = QPixmap(dragWidget->size());
    dragWidget->render(&pixmap);
    drag->setPixmap(pixmap);

    auto image = pixmap.toImage();
    mimeData->setImageData(image);
    mimeData->setUrls({helper.imageTemporaryUrl(image)});

    if (impl->m_layout->indexOf(dragWidget) >= 0)
    {
        helper.setCurrentDragWidget(dragWidget);

        if (impl->cursorIsInContainer(this))
        {
            auto dragWidgetIndex = impl->m_layout->indexOf(dragWidget);
            helper.insertPlaceHolder(impl->m_layout, dragWidgetIndex);
            dragWidget->setVisible(false);
        }
    }

    //Note: The exec() is blocking on windows but not on linux and macOS
    drag->exec(Qt::MoveAction | Qt::CopyAction);
}

void VisualizationDragDropContainer::dragEnterEvent(QDragEnterEvent *event)
{
    if (impl->acceptMimeData(event->mimeData()))
    {
        event->acceptProposedAction();

        auto& helper = sqpApp->dragDropHelper();

        if (!impl->hasPlaceHolder())
        {      
            auto dragWidget = helper.getCurrentDragWidget();
            auto parentWidget = qobject_cast<VisualizationDragDropContainer*>(dragWidget->parentWidget());
            if (parentWidget)
            {
                dragWidget->setVisible(false);
            }

            auto dragWidgetHovered = impl->getChildDragWidgetAt(this, event->pos());

            if (dragWidgetHovered)
            {
                auto hoveredWidgetIndex = impl->m_layout->indexOf(dragWidgetHovered);
                auto dragWidgetIndex = impl->m_layout->indexOf(helper.getCurrentDragWidget());
                if (dragWidgetIndex >= 0 && dragWidgetIndex <= hoveredWidgetIndex)
                    hoveredWidgetIndex += 1; //Correction of the index if the drop occurs in the same container

                helper.insertPlaceHolder(impl->m_layout, hoveredWidgetIndex);
            }
            else
            {
                helper.insertPlaceHolder(impl->m_layout, 0);
            }
        }
    }
    else
        event->ignore();

    QWidget::dragEnterEvent(event);
}

void VisualizationDragDropContainer::dragLeaveEvent(QDragLeaveEvent *event)
{
    Q_UNUSED(event);

    auto& helper = sqpApp->dragDropHelper();

    if (!impl->cursorIsInContainer(this))
    {
        helper.removePlaceHolder();

        bool isInternal = true;
        if (isInternal)
        {
            //Only if the drag is strated from the visualization
            //Show the drag widget at its original place
            //So the drag widget doesn't stay hidden if the drop occurs outside the visualization drop zone
            //(It is not possible to catch a drop event outside of the application)

            auto dragWidget = sqpApp->dragDropHelper().getCurrentDragWidget();
            if (dragWidget)
            {
                dragWidget->setVisible(true);
            }
        }
    }

    QWidget::dragLeaveEvent(event);
}

void VisualizationDragDropContainer::dragMoveEvent(QDragMoveEvent *event)
{
    if (impl->acceptMimeData(event->mimeData()))
    {
        auto dragWidgetHovered = impl->getChildDragWidgetAt(this, event->pos());
        if (dragWidgetHovered)
        {
            auto canMerge = impl->allowMergeMimeData(event->mimeData());

            auto nbDragWidget = countDragWidget();
            if (nbDragWidget > 0)
            {
                auto graphHeight = size().height() / nbDragWidget;
                auto dropIndex = floor(event->pos().y() / graphHeight);
                auto zoneSize = qMin(graphHeight / 3.0, 150.0);

                auto isOnTop = event->pos().y() < dropIndex * graphHeight + zoneSize;
                auto isOnBottom = event->pos().y() > (dropIndex + 1) * graphHeight - zoneSize;

                auto& helper = sqpApp->dragDropHelper();
                auto placeHolderIndex = impl->m_layout->indexOf(&(helper.placeHolder()));

                if (isOnTop || isOnBottom)
                {
                    if (isOnBottom)
                        dropIndex += 1;

                    auto dragWidgetIndex = impl->m_layout->indexOf(helper.getCurrentDragWidget());
                    if (dragWidgetIndex >= 0 && dragWidgetIndex <= dropIndex)
                        dropIndex += 1; //Correction of the index if the drop occurs in the same container

                    if (dropIndex != placeHolderIndex)
                    {
                        helper.insertPlaceHolder(impl->m_layout, dropIndex);
                    }
                }
                else if (canMerge)
                {
                    //drop on the middle -> merge
                    if (impl->hasPlaceHolder())
                    {
                        helper.removePlaceHolder();
                    }
                }
            }
        }
    }
    else
        event->ignore();

    QWidget::dragMoveEvent(event);
}

void VisualizationDragDropContainer::dropEvent(QDropEvent *event)
{
    if (impl->acceptMimeData(event->mimeData()))
    {
        auto dragWidget = sqpApp->dragDropHelper().getCurrentDragWidget();
        if (impl->hasPlaceHolder() && dragWidget)
        {
            auto& helper = sqpApp->dragDropHelper();

            auto droppedIndex = impl->m_layout->indexOf(&helper.placeHolder());

            auto dragWidgetIndex = impl->m_layout->indexOf(dragWidget);
            if (dragWidgetIndex >= 0 && dragWidgetIndex < droppedIndex)
                droppedIndex -= 1; //Correction of the index if the drop occurs in the same container

            dragWidget->setVisible(true);
            dragWidget->setStyleSheet("");

            event->acceptProposedAction();

            helper.removePlaceHolder();

            emit dropOccured(droppedIndex, event->mimeData());
        }
    }
    else
        event->ignore();

    QWidget::dropEvent(event);
}
