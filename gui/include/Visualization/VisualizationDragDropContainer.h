#ifndef SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
#define SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QMimeData>
#include <QVBoxLayout>
#include <QWidget>

#include <functional>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationDragDropContainer)

class VisualizationDragWidget;

class VisualizationDragDropContainer : public QWidget {
    Q_OBJECT

signals:
    void dropOccured(int dropIndex, const QMimeData *mimeData);

public:
    using AcceptMimeDataFunction = std::function<bool(const QMimeData *mimeData)>;

    VisualizationDragDropContainer(QWidget *parent = nullptr);

    void addDragWidget(VisualizationDragWidget *dragWidget);
    void insertDragWidget(int index, VisualizationDragWidget *dragWidget);

    void setAcceptedMimeTypes(const QStringList &mimeTypes);
    void setMergeAllowedMimeTypes(const QStringList &mimeTypes);

    int countDragWidget() const;

    void setAcceptMimeDataFunction(AcceptMimeDataFunction fun);

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
