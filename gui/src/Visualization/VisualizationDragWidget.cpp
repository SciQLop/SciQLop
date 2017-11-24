#include "Visualization/VisualizationDragWidget.h"
#include "Visualization/VisualizationDragDropContainer.h"

#include <QApplication>
#include <QMouseEvent>

#include <SqpApplication.h>

struct VisualizationDragWidget::VisualizationDragWidgetPrivate {

    QPoint m_DragStartPosition;
    bool m_DragStartPositionValid = false;

    explicit VisualizationDragWidgetPrivate() {}
};

VisualizationDragWidget::VisualizationDragWidget(QWidget *parent)
        : QWidget{parent}, impl{spimpl::make_unique_impl<VisualizationDragWidgetPrivate>()}
{
}

virtual QPixmap VisualizationDragWidget::customDragPixmap(const QPoint &dragPosition)
{
    Q_UNUSED(dragPosition);
    return QPixmap();
}

void VisualizationDragWidget::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        impl->m_DragStartPosition = event->pos();
    }

    impl->m_DragStartPositionValid = isDragAllowed();

    QWidget::mousePressEvent(event);
}

void VisualizationDragWidget::mouseMoveEvent(QMouseEvent *event)
{
    if (!impl->m_DragStartPositionValid || !isDragAllowed()) {
        return;
    }

    if (!(event->buttons() & Qt::LeftButton)) {
        return;
    }

    if (sqpApp->plotsInteractionMode() == SqpApplication::PlotsInteractionMode::DragAndDrop
        || event->modifiers().testFlag(Qt::AltModifier)) {

        if ((event->pos() - impl->m_DragStartPosition).manhattanLength()
            < QApplication::startDragDistance()) {
            return;
        }

        emit dragDetected(this, impl->m_DragStartPosition);
    }

    QWidget::mouseMoveEvent(event);
}
