#ifndef SCIQLOP_DRAGDROPHELPER_H
#define SCIQLOP_DRAGDROPHELPER_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QWidget>

class QVBoxLayout;
class QScrollArea;
class VisualizationDragWidget;
class VisualizationDragDropContainer;
class QMimeData;

Q_DECLARE_LOGGING_CATEGORY(LOG_DragDropHelper)

/**
 * @brief Helper class for drag&drop operations.
 * @note The helper is accessible from the sqpApp singleton and  has the same life as the whole
 * application (like a controller). But contrary to a controller, it doesn't live in a thread and
 * can interect with the gui.
 * @see SqpApplication
 */
class DragDropHelper {
public:
    static const QString MIME_TYPE_GRAPH;
    static const QString MIME_TYPE_ZONE;

    DragDropHelper();
    virtual ~DragDropHelper();

    /// Resets some internal variables. Must be called before any new drag&drop operation.
    void resetDragAndDrop();

    /// Sets the visualization widget currently being drag on the visualization.
    void setCurrentDragWidget(VisualizationDragWidget *dragWidget);

    /// Returns the visualization widget currently being drag on the visualization.
    /// Can be null if a new visualization widget is intended to be created by the drag&drop
    /// operation.
    VisualizationDragWidget *getCurrentDragWidget() const;

    QWidget &placeHolder() const;
    void insertPlaceHolder(QVBoxLayout *layout, int index);
    void removePlaceHolder();
    bool isPlaceHolderSet() const;

    /// Checks if the specified mime data is valid for a drop in the visualization
    bool checkMimeDataForVisualization(const QMimeData *mimeData,
                                       VisualizationDragDropContainer *dropContainer);

    void addDragDropScrollArea(QScrollArea *scrollArea);
    void removeDragDropScrollArea(QScrollArea *scrollArea);

    QUrl imageTemporaryUrl(const QImage &image) const;

    void setHightlightedDragWidget(VisualizationDragWidget *dragWidget);
    VisualizationDragWidget *getHightlightedDragWidget() const;

private:
    class DragDropHelperPrivate;
    spimpl::unique_impl_ptr<DragDropHelperPrivate> impl;
};

/**
 * @brief Event filter class which manage the scroll of QScrollArea during a drag&drop operation.
 * @note A QScrollArea inside an other QScrollArea is not fully supported.
 */
class DragDropScroller : public QObject {
    Q_OBJECT

public:
    DragDropScroller(QObject *parent = nullptr);

    void addScrollArea(QScrollArea *scrollArea);
    void removeScrollArea(QScrollArea *scrollArea);

protected:
    bool eventFilter(QObject *obj, QEvent *event);

private:
    class DragDropScrollerPrivate;
    spimpl::unique_impl_ptr<DragDropScrollerPrivate> impl;

private slots:
    void onTimer();
};

#endif // SCIQLOP_DRAGDROPHELPER_H
