#include "Visualization/VisualizationDragDropContainer.h"
#include "DragAndDrop/DragDropGuiController.h"
#include "SqpApplication.h"
#include "Visualization/VisualizationDragWidget.h"

#include "Common/VisualizationDef.h"

#include <QDrag>
#include <QDragEnterEvent>
#include <QVBoxLayout>

#include <cmath>
#include <memory>

Q_LOGGING_CATEGORY(LOG_VisualizationDragDropContainer, "VisualizationDragDropContainer")

auto DRAGGED_MINIATURE_WIDTH = 200; // in pixels

struct VisualizationDragDropContainer::VisualizationDragDropContainerPrivate
{

    QVBoxLayout* m_Layout;
    QHash<QString, VisualizationDragDropContainer::DropBehavior> m_AcceptedMimeTypes;
    QString m_PlaceHolderText;
    DragDropGuiController::PlaceHolderType m_PlaceHolderType;

    VisualizationDragDropContainer::AcceptMimeDataFunction m_AcceptMimeDataFun
        = [](auto mimeData) { return true; };
    VisualizationDragDropContainer::AcceptDragWidgetFunction m_AcceptDragWidgetFun
        = [](auto dragWidget, auto mimeData) { return true; };

    int m_MinContainerHeight = 0;

    explicit VisualizationDragDropContainerPrivate(QWidget* widget)
            : m_PlaceHolderType(DragDropGuiController::PlaceHolderType::Graph)
    {
        m_Layout = new QVBoxLayout(widget);
        m_Layout->setContentsMargins(0, 0, 0, 0);
    }

    bool acceptMimeData(const QMimeData* data) const
    {
        auto accepted = false;
        for (auto it = m_AcceptedMimeTypes.constBegin(); it != m_AcceptedMimeTypes.constEnd(); ++it)
        {
            const auto& type = it.key();
            const auto& behavior = it.value();

            if (data->hasFormat(type))
            {
                if (behavior != DropBehavior::Forbidden)
                {
                    accepted = true;
                }
                else
                {
                    accepted = false;
                    break;
                }
            }
        }

        if (accepted)
        {
            accepted = m_AcceptMimeDataFun(data);
        }

        return accepted;
    }

    bool allowMergeForMimeData(const QMimeData* data) const
    {
        auto result = false;
        for (auto it = m_AcceptedMimeTypes.constBegin(); it != m_AcceptedMimeTypes.constEnd(); ++it)
        {

            if (data->hasFormat(it.key())
                && (it.value() == VisualizationDragDropContainer::DropBehavior::Merged
                       || it.value()
                           == VisualizationDragDropContainer::DropBehavior::InsertedAndMerged))
            {
                result = true;
            }
            else if (data->hasFormat(it.key())
                && it.value() == VisualizationDragDropContainer::DropBehavior::Inserted)
            {
                // Merge is forbidden if the mime data contain an acceptable type which cannot be
                // merged
                result = false;
                break;
            }
        }

        return result;
    }

    bool allowInsertForMimeData(const QMimeData* data) const
    {
        for (auto it = m_AcceptedMimeTypes.constBegin(); it != m_AcceptedMimeTypes.constEnd(); ++it)
        {
            if (data->hasFormat(it.key())
                && (it.value() == VisualizationDragDropContainer::DropBehavior::Inserted
                       || it.value()
                           == VisualizationDragDropContainer::DropBehavior::InsertedAndMerged))
            {
                return true;
            }
        }

        return false;
    }

    bool hasPlaceHolder() const
    {
        return sqpApp->dragDropGuiController().placeHolder().parentWidget()
            == m_Layout->parentWidget();
    }

    VisualizationDragWidget* getChildDragWidgetAt(const QWidget* parent, const QPoint& pos) const
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
        auto widgetUnderMouse = sqpApp->widgetAt(QCursor::pos());
        return container->isAncestorOf(widgetUnderMouse) && widgetUnderMouse != container
            && sqpApp->dragDropGuiController().placeHolder().isAncestorOf(widgetUnderMouse);
    }

    int countDragWidget(const QWidget* parent, bool onlyVisible = false) const
    {
        auto nbGraph = 0;
        for (auto child : parent->children())
        {
            if (qobject_cast<VisualizationDragWidget*>(child))
            {
                if (!onlyVisible || qobject_cast<VisualizationDragWidget*>(child)->isVisible())
                {
                    nbGraph += 1;
                }
            }
        }

        return nbGraph;
    }

    bool findPlaceHolderPosition(const QPoint& pos, const QMimeData* mimeData, bool canInsert,
        bool canMerge, const VisualizationDragDropContainer* container);
};

VisualizationDragDropContainer::VisualizationDragDropContainer(QWidget* parent)
        : QFrame { parent }
        , impl { spimpl::make_unique_impl<VisualizationDragDropContainerPrivate>(this) }
{
    setAcceptDrops(true);
}

void VisualizationDragDropContainer::addDragWidget(VisualizationDragWidget* dragWidget)
{
    impl->m_Layout->addWidget(dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this,
        &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::insertDragWidget(
    int index, VisualizationDragWidget* dragWidget)
{
    impl->m_Layout->insertWidget(index, dragWidget);
    disconnect(dragWidget, &VisualizationDragWidget::dragDetected, nullptr, nullptr);
    connect(dragWidget, &VisualizationDragWidget::dragDetected, this,
        &VisualizationDragDropContainer::startDrag);
}

void VisualizationDragDropContainer::setMimeType(
    const QString& mimeType, VisualizationDragDropContainer::DropBehavior behavior)
{
    impl->m_AcceptedMimeTypes[mimeType] = behavior;
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

void VisualizationDragDropContainer::setAcceptDragWidgetFunction(
    VisualizationDragDropContainer::AcceptDragWidgetFunction fun)
{
    impl->m_AcceptDragWidgetFun = fun;
}

void VisualizationDragDropContainer::setPlaceHolderType(
    DragDropGuiController::PlaceHolderType type, const QString& placeHolderText)
{
    impl->m_PlaceHolderType = type;
    impl->m_PlaceHolderText = placeHolderText;
}

void VisualizationDragDropContainer::startDrag(
    VisualizationDragWidget* dragWidget, const QPoint& dragPosition)
{
    auto& helper = sqpApp->dragDropGuiController();
    helper.resetDragAndDrop();

    // Note: The management of the drag object is done by Qt
    auto drag = new QDrag { dragWidget };

    auto mimeData = dragWidget->mimeData(dragPosition);
    drag->setMimeData(mimeData);

    auto pixmap = dragWidget->customDragPixmap(dragPosition);
    if (pixmap.isNull())
    {
        pixmap = QPixmap { dragWidget->size() };
        dragWidget->render(&pixmap);
    }

    drag->setPixmap(pixmap.scaled(DRAGGED_MINIATURE_WIDTH, DRAGGED_MINIATURE_WIDTH,
        Qt::KeepAspectRatio, Qt::SmoothTransformation));

    auto image = pixmap.toImage();
    mimeData->setImageData(image);
    mimeData->setUrls({ helper.imageTemporaryUrl(image) });

    if (impl->m_Layout->indexOf(dragWidget) >= 0)
    {

        if (impl->acceptMimeData(mimeData) && impl->allowInsertForMimeData(mimeData))
        {
            helper.setCurrentDragWidget(dragWidget);

            if (impl->cursorIsInContainer(this))
            {
                auto dragWidgetIndex = impl->m_Layout->indexOf(dragWidget);
                helper.insertPlaceHolder(impl->m_Layout, dragWidgetIndex, impl->m_PlaceHolderType,
                    impl->m_PlaceHolderText);
                dragWidget->setVisible(false);
            }
            else
            {
                // The drag starts directly outside the drop zone
                // do not add the placeHolder
            }
        }

        drag->exec(Qt::MoveAction | Qt::CopyAction, Qt::MoveAction);

        helper.doCloseWidgets();
    }
    else
    {
        qCWarning(LOG_VisualizationDragDropContainer())
            << tr("VisualizationDragDropContainer::startDrag, drag aborted, the specified "
                  "VisualizationDragWidget is not found in this container.");
    }
}

void VisualizationDragDropContainer::dragEnterEvent(QDragEnterEvent* event)
{
    if (impl->acceptMimeData(event->mimeData()))
    {
        event->acceptProposedAction();

        auto& helper = sqpApp->dragDropGuiController();

        if (!impl->hasPlaceHolder())
        {
            auto dragWidget = helper.getCurrentDragWidget();

            if (dragWidget)
            {
                // If the drag&drop is internal to the visualization, entering the container hide
                // the dragWidget which was made visible by the dragLeaveEvent
                auto parentWidget
                    = qobject_cast<VisualizationDragDropContainer*>(dragWidget->parentWidget());
                if (parentWidget)
                {
                    dragWidget->setVisible(false);
                }
            }

            auto canMerge = impl->allowMergeForMimeData(event->mimeData());
            auto canInsert = impl->allowInsertForMimeData(event->mimeData());
            if (!impl->findPlaceHolderPosition(
                    event->pos(), event->mimeData(), canInsert, canMerge, this))
            {
                event->ignore();
            }
        }
        else
        {
            // do nothing
        }
    }
    else
    {
        event->ignore();
    }

    QWidget::dragEnterEvent(event);
}

void VisualizationDragDropContainer::dragLeaveEvent(QDragLeaveEvent* event)
{
    Q_UNUSED(event);

    auto& helper = sqpApp->dragDropGuiController();

    if (!impl->cursorIsInContainer(this))
    {
        helper.removePlaceHolder();
        helper.setHightlightedDragWidget(nullptr);
        impl->m_MinContainerHeight = 0;

        auto dragWidget = helper.getCurrentDragWidget();
        if (dragWidget)
        {
            // dragWidget has a value only if the drag is started from the visualization
            // In that case, shows the drag widget at its original place
            // So the drag widget doesn't stay hidden if the drop occurs outside the visualization
            // drop zone (It is not possible to catch a drop event outside of the application)

            if (dragWidget)
            {
                dragWidget->setVisible(true);
            }
        }
    }
    else
    {
        // Leave event probably received for a child widget.
        // Do nothing.
        // Note: The DragLeave event, doesn't have any mean to determine who sent it.
    }

    QWidget::dragLeaveEvent(event);
}

void VisualizationDragDropContainer::dragMoveEvent(QDragMoveEvent* event)
{
    if (impl->acceptMimeData(event->mimeData()))
    {
        event->acceptProposedAction();
        auto canMerge = impl->allowMergeForMimeData(event->mimeData());
        auto canInsert = impl->allowInsertForMimeData(event->mimeData());
        impl->findPlaceHolderPosition(event->pos(), event->mimeData(), canInsert, canMerge, this);
    }
    else
    {
        event->ignore();
    }

    QWidget::dragMoveEvent(event);
}

void VisualizationDragDropContainer::dropEvent(QDropEvent* event)
{
    auto& helper = sqpApp->dragDropGuiController();

    if (impl->acceptMimeData(event->mimeData()))
    {
        auto dragWidget = helper.getCurrentDragWidget();
        if (impl->hasPlaceHolder())
        {
            // drop where the placeHolder is located

            auto canInsert = impl->allowInsertForMimeData(event->mimeData());
            if (canInsert)
            {
                auto droppedIndex = impl->m_Layout->indexOf(&helper.placeHolder());

                if (dragWidget)
                {
                    auto dragWidgetIndex = impl->m_Layout->indexOf(dragWidget);
                    if (dragWidgetIndex >= 0 && dragWidgetIndex < droppedIndex)
                    {
                        // Correction of the index if the drop occurs in the same container
                        // and if the drag is started from the visualization (in that case, the
                        // dragWidget is hidden)
                        droppedIndex -= 1;
                    }

                    dragWidget->setVisible(true);
                }

                event->acceptProposedAction();

                helper.removePlaceHolder();

                emit dropOccuredInContainer(droppedIndex, event->mimeData());
            }
            else
            {
                qCWarning(LOG_VisualizationDragDropContainer()) << tr(
                    "VisualizationDragDropContainer::dropEvent, dropping on the placeHolder, but "
                    "the insertion is forbidden.");
                Q_ASSERT(false);
            }
        }
        else if (helper.getHightlightedDragWidget())
        {
            // drop on the highlighted widget

            auto canMerge = impl->allowMergeForMimeData(event->mimeData());
            if (canMerge)
            {
                event->acceptProposedAction();
                emit dropOccuredOnWidget(helper.getHightlightedDragWidget(), event->mimeData());
            }
            else
            {
                qCWarning(LOG_VisualizationDragDropContainer())
                    << tr("VisualizationDragDropContainer::dropEvent, dropping on a widget, but "
                          "the merge is forbidden.");
                Q_ASSERT(false);
            }
        }
    }
    else
    {
        event->ignore();
    }

    sqpApp->dragDropGuiController().setHightlightedDragWidget(nullptr);
    impl->m_MinContainerHeight = 0;

    QWidget::dropEvent(event);
}


bool VisualizationDragDropContainer::VisualizationDragDropContainerPrivate::findPlaceHolderPosition(
    const QPoint& pos, const QMimeData* mimeData, bool canInsert, bool canMerge,
    const VisualizationDragDropContainer* container)
{
    auto& helper = sqpApp->dragDropGuiController();

    auto absPos = container->mapToGlobal(pos);
    auto isOnPlaceHolder = helper.placeHolder().isAncestorOf(sqpApp->widgetAt(absPos));

    if (countDragWidget(container, true) == 0)
    {
        // Drop on an empty container, just add the placeHolder at the top
        helper.insertPlaceHolder(m_Layout, 0, m_PlaceHolderType, m_PlaceHolderText);
    }
    else if (!isOnPlaceHolder)
    {
        auto nbDragWidget = countDragWidget(container);
        if (nbDragWidget > 0)
        {

            if (m_MinContainerHeight == 0)
            {
                m_MinContainerHeight = container->size().height();
            }

            m_MinContainerHeight = qMin(m_MinContainerHeight, container->size().height());
            auto graphHeight = qMax(m_MinContainerHeight / nbDragWidget, GRAPH_MINIMUM_HEIGHT);

            auto posY = pos.y();
            auto dropIndex = floor(posY / graphHeight);
            auto zoneSize = graphHeight / 4.0;


            auto isOnTop = posY < dropIndex * graphHeight + zoneSize;
            auto isOnBottom = posY > (dropIndex + 1) * graphHeight - zoneSize;

            auto placeHolderIndex = m_Layout->indexOf(&(helper.placeHolder()));

            auto dragWidgetHovered = getChildDragWidgetAt(container, pos);

            auto acceptMerge = m_AcceptDragWidgetFun(dragWidgetHovered, mimeData);

            if (canInsert && (isOnTop || isOnBottom || !canMerge || !acceptMerge))
            {
                if (posY > (dropIndex + 1) * graphHeight - graphHeight / 2.0)
                {
                    dropIndex += 1;
                }

                if (helper.getCurrentDragWidget())
                {
                    auto dragWidgetIndex = m_Layout->indexOf(helper.getCurrentDragWidget());
                    if (dragWidgetIndex >= 0 && dragWidgetIndex <= dropIndex)
                    {
                        // Correction of the index if the drop occurs in the same container
                        // and if the drag is started from the visualization (in that case, the
                        // dragWidget is hidden)
                        dropIndex += 1;
                    }
                }

                if (dropIndex != placeHolderIndex)
                {
                    helper.insertPlaceHolder(
                        m_Layout, dropIndex, m_PlaceHolderType, m_PlaceHolderText);
                }

                helper.setHightlightedDragWidget(nullptr);
            }
            else if (canMerge && dragWidgetHovered)
            {
                // drop on the middle -> merge
                if (hasPlaceHolder())
                {
                    helper.removePlaceHolder();
                }

                helper.setHightlightedDragWidget(dragWidgetHovered);
            }
            else
            {
                qCWarning(LOG_VisualizationDragDropContainer())
                    << tr("VisualizationDragDropContainer::findPlaceHolderPosition, no valid drop "
                          "action.");
            }
        }
        else
        {
            qCInfo(LOG_VisualizationDragDropContainer())
                << tr("VisualizationDragDropContainer::findPlaceHolderPosition, no widget "
                      "found in the "
                      "container");
        }
    }
    else
    {
        // the mouse is hover the placeHolder
        // Do nothing
    }

    return true;
}
