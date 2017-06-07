#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include <QWidget>

namespace Ui {
class VisualizationGraphWidget;
} // namespace Ui

class VisualizationGraphWidget : public QWidget {
    Q_OBJECT

public:
    explicit VisualizationGraphWidget(QWidget *parent = 0);
    virtual ~VisualizationGraphWidget();

private:
    Ui::VisualizationGraphWidget *ui;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
