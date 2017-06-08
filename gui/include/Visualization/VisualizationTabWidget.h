#ifndef SCIQLOP_VISUALIZATIONTABWIDGET_H
#define SCIQLOP_VISUALIZATIONTABWIDGET_H

#include <QWidget>

namespace Ui {
class VisualizationTabWidget;
} // namespace Ui

class VisualizationTabWidget : public QWidget {
    Q_OBJECT

public:
    explicit VisualizationTabWidget(QWidget *parent = 0);
    virtual ~VisualizationTabWidget();

private:
    Ui::VisualizationTabWidget *ui;
};

#endif // SCIQLOP_VISUALIZATIONTABWIDGET_H
