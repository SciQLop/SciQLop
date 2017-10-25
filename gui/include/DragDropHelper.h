#ifndef DRAGDROPHELPER_H
#define DRAGDROPHELPER_H

#include <Common/spimpl.h>
#include <QWidget>

class QVBoxLayout;
class QScrollArea;
class VisualizationDragWidget;
class QMimeData;

/**
 * @brief Helper class for drag&drop operations.
 */
class DragDropHelper
{
public:
    DragDropHelper();
    ~DragDropHelper();

    static const QString MIME_TYPE_GRAPH;
    static const QString MIME_TYPE_ZONE;

    void setCurrentDragWidget(VisualizationDragWidget* dragWidget);
    VisualizationDragWidget* getCurrentDragWidget() const;

    QWidget &placeHolder() const;
    void insertPlaceHolder(QVBoxLayout* layout, int index);
    void removePlaceHolder();
    bool isPlaceHolderSet() const;

    void addDragDropScrollArea(QScrollArea* scrollArea);
    void removeDragDropScrollArea(QScrollArea* scrollArea);

    QUrl imageTemporaryUrl(const QImage& image) const;

private:
    class DragDropHelperPrivate;
    spimpl::unique_impl_ptr<DragDropHelperPrivate> impl;
};

#endif // DRAGDROPHELPER_H
