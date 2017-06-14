#ifndef SCIQLOP_VISUALIZATIONZONEWIDGET_H
#define SCIQLOP_VISUALIZATIONZONEWIDGET_H

#include "Visualization/IVisualizationWidget.h"

class VisualizationGraphWidget;

#include <QWidget>

namespace Ui {
class VisualizationZoneWidget;
} // Ui

class VisualizationZoneWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationZoneWidget(QWidget *parent = 0);
    virtual ~VisualizationZoneWidget();

    /// Add a graph widget
    void addGraph(VisualizationGraphWidget *graphWidget);

    /// Create a graph using a Variable
    VisualizationGraphWidget *createGraph();

    /// Remove a graph
    void removeGraph(VisualizationGraphWidget *graph);

    // IVisualizationWidget interface
    void accept(IVisualizationWidget *visitor);
    void close();
    QString name();

private:
    Ui::VisualizationZoneWidget *ui;
};

#endif // SCIQLOP_VISUALIZATIONZONEWIDGET_H
