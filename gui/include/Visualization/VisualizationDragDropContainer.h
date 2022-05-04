#ifndef SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
#define SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H

#include <Common/spimpl.h>
#include <QFrame>
#include <QLoggingCategory>
#include <QMimeData>
#include <QVBoxLayout>

#include <functional>

#include <DragAndDrop/DragDropGuiController.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationDragDropContainer)

class VisualizationDragWidget;

class VisualizationDragDropContainer : public QFrame {
    Q_OBJECT

signals:
    void dropOccuredInContainer(int dropIndex, const QMimeData *mimeData);
    void dropOccuredOnWidget(VisualizationDragWidget *dragWidget, const QMimeData *mimeData);

public:
    enum class DropBehavior { Inserted, Merged, InsertedAndMerged, Forbidden };
    using AcceptMimeDataFunction = std::function<bool(const QMimeData *mimeData)>;
    using AcceptDragWidgetFunction
        = std::function<bool(const VisualizationDragWidget *dragWidget, const QMimeData *mimeData)>;

    VisualizationDragDropContainer(QWidget *parent = nullptr);

    void addDragWidget(VisualizationDragWidget *dragWidget);
    void insertDragWidget(int index, VisualizationDragWidget *dragWidget);

    void setMimeType(const QString &mimeType, DropBehavior behavior);

    int countDragWidget() const;

    void setAcceptMimeDataFunction(AcceptMimeDataFunction fun);

    void setAcceptDragWidgetFunction(AcceptDragWidgetFunction fun);

    void setPlaceHolderType(DragDropGuiController::PlaceHolderType type,
                            const QString &placeHolderText = QString());

protected:
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dragLeaveEvent(QDragLeaveEvent *event) override;
    void dragMoveEvent(QDragMoveEvent *event) override;
    void dropEvent(QDropEvent *event) override;

private:
    class VisualizationDragDropContainerPrivate;
    spimpl::unique_impl_ptr<VisualizationDragDropContainerPrivate> impl;

private slots:
    void startDrag(VisualizationDragWidget *dragWidget, const QPoint &dragPosition);
};

#endif // SCIQLOP_VISUALIZATIONDRAGDROPCONTAINER_H
