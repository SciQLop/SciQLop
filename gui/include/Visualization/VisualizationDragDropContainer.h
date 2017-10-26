#ifndef SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
#define SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H

#include <Common/spimpl.h>
#include <QMimeData>
#include <QVBoxLayout>
#include <QWidget>

class VisualizationDragWidget;

class VisualizationDragDropContainer : public QWidget {
    Q_OBJECT

signals:
    void dropOccured(int dropIndex, const QMimeData *mimeData);

public:
    VisualizationDragDropContainer(QWidget *parent = nullptr);

    void addDragWidget(VisualizationDragWidget *dragWidget);
    void insertDragWidget(int index, VisualizationDragWidget *dragWidget);

    void setAcceptedMimeTypes(const QStringList &mimeTypes);
    void setMergeAllowedMimeTypes(const QStringList &mimeTypes);

    int countDragWidget() const;

protected:
    void dragEnterEvent(QDragEnterEvent *event);
    void dragLeaveEvent(QDragLeaveEvent *event);
    void dragMoveEvent(QDragMoveEvent *event);
    void dropEvent(QDropEvent *event);

private:
    class VisualizationDragDropContainerPrivate;
    spimpl::unique_impl_ptr<VisualizationDragDropContainerPrivate> impl;

private slots:
    void startDrag(VisualizationDragWidget *dragWidget, const QPoint &dragPosition);
};

#endif // SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
