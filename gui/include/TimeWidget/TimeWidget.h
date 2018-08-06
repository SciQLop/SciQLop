#ifndef SCIQLOP_TIMEWIDGET_H
#define SCIQLOP_TIMEWIDGET_H

#include <QWidget>

#include <Data/SqpRange.h>

#include <Common/spimpl.h>

namespace Ui {
class TimeWidget;
} // Ui

class TimeWidget : public QWidget {
    Q_OBJECT

public:
    explicit TimeWidget(QWidget *parent = 0);
    virtual ~TimeWidget();

    void setTimeRange(DateTimeRange time);
    DateTimeRange timeRange() const;

signals:
    /// Signal emitted when the time parameters has beed updated
    void timeUpdated(DateTimeRange time);

public slots:
    /// slot called when time parameters update has ben requested
    void onTimeUpdateRequested();

protected:
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dragLeaveEvent(QDragLeaveEvent *event) override;
    void dropEvent(QDropEvent *event) override;

    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;

private:
    Ui::TimeWidget *ui;

    class TimeWidgetPrivate;
    spimpl::unique_impl_ptr<TimeWidgetPrivate> impl;
};

#endif // SCIQLOP_ SQPSIDEPANE_H
