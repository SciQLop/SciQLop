#ifndef SCIQLOP_VISUALIZATIONZONEWIDGET_H
#define SCIQLOP_VISUALIZATIONZONEWIDGET_H

#include "Visualization/IVisualizationWidget.h"
#include "Visualization/VisualizationDragWidget.h"

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationZoneWidget)

namespace Ui {
class VisualizationZoneWidget;
} // namespace Ui

class Variable;
class VisualizationGraphWidget;

class VisualizationZoneWidget : public VisualizationDragWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationZoneWidget(const QString &name = {}, QWidget *parent = 0);
    virtual ~VisualizationZoneWidget();

    /// Adds a graph widget
    void addGraph(VisualizationGraphWidget *graphWidget);

    /// Inserts a graph widget
    void insertGraph(int index, VisualizationGraphWidget *graphWidget);

    /**
     * Creates a graph using a variable. The variable will be displayed in the new graph.
     * The graph is added at the end.
     * @param variable the variable for which to create the graph
     * @return the pointer to the created graph
     */
    VisualizationGraphWidget *createGraph(std::shared_ptr<Variable> variable);

    /**
     * Creates a graph using a variable. The variable will be displayed in the new graph.
     * The graph is inserted at the specified index.
     * @param variable the variable for which to create the graph
     * @param index The index where the graph should be inserted in the layout
     * @return the pointer to the created graph
     */
    VisualizationGraphWidget *createGraph(std::shared_ptr<Variable> variable, int index);

    /**
     * Creates a graph using a list of variables. The variables will be displayed in the new graph.
     * The graph is inserted at the specified index.
     * @param variables List of variables to be added to the graph
     * @param index The index where the graph should be inserted in the layout
     * @return the pointer to the created graph
     */
    VisualizationGraphWidget *createGraph(const QList<std::shared_ptr<Variable> > variables,
                                          int index);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

    // VisualisationDragWidget
    QMimeData *mimeData(const QPoint &position) const override;
    bool isDragAllowed() const override;

    void notifyMouseMoveInGraph(const QPointF &graphPosition, const QPointF &plotPosition,
                                VisualizationGraphWidget *graphWidget);
    void notifyMouseLeaveGraph(VisualizationGraphWidget *graphWidget);

protected:
    void closeEvent(QCloseEvent *event) override;

private:
    Ui::VisualizationZoneWidget *ui;

    class VisualizationZoneWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationZoneWidgetPrivate> impl;

private slots:
    void onVariableAdded(std::shared_ptr<Variable> variable);
    /// Slot called when a variable is about to be removed from a graph contained in the zone
    void onVariableAboutToBeRemoved(std::shared_ptr<Variable> variable);

    void dropMimeData(int index, const QMimeData *mimeData);
    void dropMimeDataOnGraph(VisualizationDragWidget *dragWidget, const QMimeData *mimeData);
};

#endif // SCIQLOP_VISUALIZATIONZONEWIDGET_H
