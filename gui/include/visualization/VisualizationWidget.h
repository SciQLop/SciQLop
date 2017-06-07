#ifndef SCIQLOP_VISUALIZATIONWIDGET_H
#define SCIQLOP_VISUALIZATIONWIDGET_H

#include <QWidget>

namespace Ui {
class VisualizationWidget;
} // namespace Ui

class VisualizationWidget : public QWidget {
    Q_OBJECT

public:
    explicit VisualizationWidget(QWidget *parent = 0);
    virtual ~VisualizationWidget();

private:
    Ui::VisualizationWidget *ui;
};

#endif // VISUALIZATIONWIDGET_H
