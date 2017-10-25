#ifndef VISUALIZATIONDRAGWIDGET_H
#define VISUALIZATIONDRAGWIDGET_H

#include <QWidget>
#include <QMimeData>
#include <Common/spimpl.h>

class VisualizationDragWidget : public QWidget
{
    Q_OBJECT

public:
    VisualizationDragWidget(QWidget* parent = nullptr);

    virtual QMimeData* mimeData() const = 0;
    virtual bool isDragAllowed() const = 0;

protected:
    virtual void mousePressEvent(QMouseEvent *event) override;
    virtual void mouseMoveEvent(QMouseEvent *event) override;

private:
    class VisualizationDragWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationDragWidgetPrivate> impl;

signals:
    void dragDetected(VisualizationDragWidget* dragWidget, const QPoint& dragPosition);
};

#endif // VISUALIZATIONDRAGWIDGET_H
