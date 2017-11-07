#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include "Visualization/IVisualizationWidget.h"
#include "Visualization/VisualizationDragWidget.h"

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationGraphWidget)

class QCPRange;
class QCustomPlot;
class SqpRange;
class Variable;
class VisualizationZoneWidget;

namespace Ui {
class VisualizationGraphWidget;
} // namespace Ui

class VisualizationGraphWidget : public VisualizationDragWidget, public IVisualizationWidget {
    Q_OBJECT

    friend class QCustomPlotSynchronizer;
    friend class VisualizationGraphRenderingDelegate;

public:
    explicit VisualizationGraphWidget(const QString &name = {}, QWidget *parent = 0);
    virtual ~VisualizationGraphWidget();

    VisualizationZoneWidget *parentZoneWidget() const noexcept;

    /// If acquisition isn't enable, requestDataLoading signal cannot be emit
    void enableAcquisition(bool enable);

    void addVariable(std::shared_ptr<Variable> variable, SqpRange range);

    /// Removes a variable from the graph
    void removeVariable(std::shared_ptr<Variable> variable) noexcept;

    /// Returns the list of all variables used in the graph
    QList<std::shared_ptr<Variable> > variables() const;

    void setYRange(const SqpRange &range);
    SqpRange graphRange() const noexcept;
    void setGraphRange(const SqpRange &range);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

    // VisualisationDragWidget
    QMimeData *mimeData() const override;
    bool isDragAllowed() const override;
    void highlightForMerge(bool highlighted) override;

signals:
    void synchronize(const SqpRange &range, const SqpRange &oldRange);
    void requestDataLoading(QVector<std::shared_ptr<Variable> > variable, const SqpRange &range,
                            bool synchronise);

    /// Signal emitted when the variable is about to be removed from the graph
    void variableAboutToBeRemoved(std::shared_ptr<Variable> var);
    /// Signal emitted when the variable has been added to the graph
    void variableAdded(std::shared_ptr<Variable> var);

protected:
    void closeEvent(QCloseEvent *event) override;
    void enterEvent(QEvent *event) override;
    void leaveEvent(QEvent *event) override;

    QCustomPlot &plot() noexcept;

private:
    Ui::VisualizationGraphWidget *ui;

    class VisualizationGraphWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationGraphWidgetPrivate> impl;

private slots:
    /// Slot called when right clicking on the graph (displays a menu)
    void onGraphMenuRequested(const QPoint &pos) noexcept;

    /// Rescale the X axe to range parameter
    void onRangeChanged(const QCPRange &t1, const QCPRange &t2);

    /// Slot called when a mouse move was made
    void onMouseMove(QMouseEvent *event) noexcept;
    /// Slot called when a mouse wheel was made, to perform some processing before the zoom is done
    void onMouseWheel(QWheelEvent *event) noexcept;
    /// Slot called when a mouse press was made, to activate the calibration of a graph
    void onMousePress(QMouseEvent *event) noexcept;
    /// Slot called when a mouse release was made, to deactivate the calibration of a graph
    void onMouseRelease(QMouseEvent *event) noexcept;

    void onDataCacheVariableUpdated();

    void onUpdateVarDisplaying(std::shared_ptr<Variable> variable, const SqpRange &range);
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
