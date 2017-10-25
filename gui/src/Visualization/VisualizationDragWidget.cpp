#include "Visualization/VisualizationDragWidget.h"
#include "Visualization/VisualizationDragDropContainer.h"

#include <QMouseEvent>
#include <QApplication>

struct VisualizationDragWidget::VisualizationDragWidgetPrivate {

    QPoint m_dragStartPosition;
    bool m_dragStartPositionValid = false;

    explicit VisualizationDragWidgetPrivate()
    {
    }
};

VisualizationDragWidget::VisualizationDragWidget(QWidget* parent)
    : QWidget{parent}, impl{spimpl::make_unique_impl<VisualizationDragWidgetPrivate>()}
{

}

void VisualizationDragWidget::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton)
        impl->m_dragStartPosition = event->pos();

    impl->m_dragStartPositionValid = isDragAllowed();

    QWidget::mousePressEvent(event);
}

void VisualizationDragWidget::mouseMoveEvent(QMouseEvent *event)
{
    if (!impl->m_dragStartPositionValid || !isDragAllowed())
        return;

    if (!(event->buttons() & Qt::LeftButton))
        return;

    if (!event->modifiers().testFlag(Qt::AltModifier))
        return;

    if ((event->pos() - impl->m_dragStartPosition).manhattanLength() < QApplication::startDragDistance())
        return;

    emit dragDetected(this, impl->m_dragStartPosition);

    QWidget::mouseMoveEvent(event);
}
