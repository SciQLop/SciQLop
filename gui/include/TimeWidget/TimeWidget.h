#ifndef SCIQLOP_TIMEWIDGET_H
#define SCIQLOP_TIMEWIDGET_H

#include <QWidget>

#include <Data/SqpRange.h>

namespace Ui {
class TimeWidget;
} // Ui

class TimeWidget : public QWidget {
    Q_OBJECT

public:
    explicit TimeWidget(QWidget *parent = 0);
    virtual ~TimeWidget();

signals:
    /// Signal emitted when the time parameters has beed updated
    void timeUpdated(SqpRange time);

public slots:
    /// slot called when time parameters update has ben requested
    void onTimeUpdateRequested();


private:
    Ui::TimeWidget *ui;
};

#endif // SCIQLOP_ SQPSIDEPANE_H
