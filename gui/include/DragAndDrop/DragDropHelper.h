#ifndef SCIQLOP_DRAGDROPHELPER_H
#define SCIQLOP_DRAGDROPHELPER_H

#include <Common/spimpl.h>
#include <QLoggingCategory>
#include <QWidget>

class QVBoxLayout;
class QScrollArea;
class QTabBar;
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

    enum class PlaceHolderType { Default, Graph, Zone };

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
    void insertPlaceHolder(QVBoxLayout *layout, int index, PlaceHolderType type,
                           const QString &topLabelText);
    void removePlaceHolder();
    bool isPlaceHolderSet() const;

    /// Checks if the specified mime data is valid for a drop in the visualization
    bool checkMimeDataForVisualization(const QMimeData *mimeData,
                                       VisualizationDragDropContainer *dropContainer);

    void addDragDropScrollArea(QScrollArea *scrollArea);
    void removeDragDropScrollArea(QScrollArea *scrollArea);

    void addDragDropTabBar(QTabBar *tabBar);
    void removeDragDropTabBar(QTabBar *tabBar);

    QUrl imageTemporaryUrl(const QImage &image) const;

    void setHightlightedDragWidget(VisualizationDragWidget *dragWidget);
    VisualizationDragWidget *getHightlightedDragWidget() const;

private:
    class DragDropHelperPrivate;
    spimpl::unique_impl_ptr<DragDropHelperPrivate> impl;
};

#endif // SCIQLOP_DRAGDROPHELPER_H
