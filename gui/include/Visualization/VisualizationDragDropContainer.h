#ifndef SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
#define SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H

#include <Common/spimpl.h>
#include <QFrame>
#include <QLoggingCategory>
#include <QMimeData>
#include <QVBoxLayout>

#include <functional>

#include <DragAndDrop/DragDropHelper.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationDragDropContainer)

class VisualizationDragWidget;

class VisualizationDragDropContainer : public QFrame {
    Q_OBJECT

signals:
    void dropOccuredInContainer(int dropIndex, const QMimeData *mimeData);
    void dropOccuredOnWidget(VisualizationDragWidget *dragWidget, const QMimeData *mimeData);

public:
    enum class DropBehavior { Inserted, Merged, InsertedAndMerged };
    using AcceptMimeDataFunction = std::function<bool(const QMimeData *mimeData)>;

    VisualizationDragDropContainer(QWidget *parent = nullptr);

    void addDragWidget(VisualizationDragWidget *dragWidget);
    void insertDragWidget(int index, VisualizationDragWidget *dragWidget);

    void addAcceptedMimeType(const QString &mimeType, DropBehavior behavior);

    int countDragWidget() const;

    void setAcceptMimeDataFunction(AcceptMimeDataFunction fun);

    void setPlaceHolderType(DragDropHelper::PlaceHolderType type,
                            const QString &placeHolderText = QString());

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
