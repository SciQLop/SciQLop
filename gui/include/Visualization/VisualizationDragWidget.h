#ifndef SCIQLOP_VISUALIZATIONDRAGWIDGET_H
#define SCIQLOP_VISUALIZATIONDRAGWIDGET_H

#include <Common/spimpl.h>
#include <QMimeData>
#include <QWidget>

class VisualizationDragWidget : public QWidget {
    Q_OBJECT

public:
    VisualizationDragWidget(QWidget *parent = nullptr);

    virtual QMimeData *mimeData(const QPoint &position) const = 0;
    virtual bool isDragAllowed() const = 0;
    virtual void highlightForMerge(bool highlighted) { Q_UNUSED(highlighted); }

    /// Custom pixmap to display during a drag operation.
    /// If the provided pixmap is null, a pixmap of the entire widget is used.
    virtual QPixmap customDragPixmap(const QPoint &dragPosition);

protected:
    virtual void mousePressEvent(QMouseEvent *event) override;
    virtual void mouseMoveEvent(QMouseEvent *event) override;

private:
    class VisualizationDragWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationDragWidgetPrivate> impl;

signals:
    void dragDetected(VisualizationDragWidget *dragWidget, const QPoint &dragPosition);
};

#endif // SCIQLOP_VISUALIZATIONDRAGWIDGET_H
