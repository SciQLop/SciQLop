#ifndef SCIQLOP_SQPSIDEPANE_H
#define SCIQLOP_SQPSIDEPANE_H

#include <QWidget>

namespace Ui {
class SqpSidePane;
} // Ui

class QToolBar;

class SqpSidePane : public QWidget {
    Q_OBJECT

public:
    explicit SqpSidePane(QWidget *parent = 0);
    virtual ~SqpSidePane();

    QToolBar *sidePane();

private:
    Ui::SqpSidePane *ui;

    QToolBar *m_SidePaneToolbar;
};

#endif // SCIQLOP_ SQPSIDEPANE_H
