#ifndef SCIQLOP_VISUALIZATIONZONEWIDGET_H
#define SCIQLOP_VISUALIZATIONZONEWIDGET_H

#include <QWidget>

namespace Ui {
class VisualizationZoneWidget;
} // Ui

class VisualizationZoneWidget : public QWidget {
    Q_OBJECT

public:
    explicit VisualizationZoneWidget(QWidget *parent = 0);
    virtual ~VisualizationZoneWidget();

private:
    Ui::VisualizationZoneWidget *ui;
};

#endif // SCIQLOP_VISUALIZATIONZONEWIDGET_H
