#ifndef SCIQLOP_VISUALIZATIONZONEWIDGET_H
#define SCIQLOP_VISUALIZATIONZONEWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationZoneWidget)

namespace Ui {
class VisualizationZoneWidget;
} // Ui

class Variable;
class VisualizationGraphWidget;

class VisualizationZoneWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationZoneWidget(const QString &name = {}, QWidget *parent = 0);
    virtual ~VisualizationZoneWidget();

    /// Add a graph widget
    void addGraph(VisualizationGraphWidget *graphWidget);

    /**
     * Creates a graph using a variable. The variable will be displayed in the new graph.
     * @param variable the variable for which to create the graph
     * @return the pointer to the created graph
     */
    VisualizationGraphWidget *createGraph(std::shared_ptr<Variable> variable);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

private:
    Ui::VisualizationZoneWidget *ui;

    class VisualizationZoneWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationZoneWidgetPrivate> impl;

private slots:
    void onVariableAdded(std::shared_ptr<Variable> variable);
    /// Slot called when a variable is about to be removed from a graph contained in the zone
    void onVariableAboutToBeRemoved(std::shared_ptr<Variable> variable);
};

#endif // SCIQLOP_VISUALIZATIONZONEWIDGET_H
