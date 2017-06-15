#ifndef SCIQLOP_TIMEWIDGET_H
#define SCIQLOP_TIMEWIDGET_H

#include <QWidget>

namespace Ui {
class TimeWidget;
} // Ui

class TimeWidget : public QWidget {
    Q_OBJECT

public:
    explicit TimeWidget(QWidget *parent = 0);
    virtual ~TimeWidget();

private:
    Ui::TimeWidget *ui;
};

#endif // SCIQLOP_ SQPSIDEPANE_H
