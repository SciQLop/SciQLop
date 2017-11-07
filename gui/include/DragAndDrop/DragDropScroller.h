#ifndef SCIQLOP_DRAGDROPSCROLLER_H
#define SCIQLOP_DRAGDROPSCROLLER_H

#include <Common/spimpl.h>
#include <QScrollArea>

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


#endif // SCIQLOP_DRAGDROPSCROLLER_H
