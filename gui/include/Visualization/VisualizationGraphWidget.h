#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationGraphWidget)

class QCPRange;
class SqpDateTime;
class Variable;

namespace Ui {
class VisualizationGraphWidget;
} // namespace Ui

class VisualizationGraphWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationGraphWidget(const QString &name = {}, QWidget *parent = 0);
    virtual ~VisualizationGraphWidget();

    void addVariable(std::shared_ptr<Variable> variable);
    void addVariableUsingGraph(std::shared_ptr<Variable> variable);
    /// Removes a variable from the graph
    void removeVariable(std::shared_ptr<Variable> variable) noexcept;

    /// Rescale the X axe to range parameter
    void setRange(std::shared_ptr<Variable> variable, const SqpDateTime &range);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

signals:
    void requestDataLoading(std::shared_ptr<Variable> variable, const SqpDateTime &dateTime);


private:
    Ui::VisualizationGraphWidget *ui;

    class VisualizationGraphWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationGraphWidgetPrivate> impl;

private slots:
    /// Slot called when right clicking on the graph (displays a menu)
    void onGraphMenuRequested(const QPoint &pos) noexcept;

    void onRangeChanged(const QCPRange &t1);

    /// Slot called when a mouse wheel was made, to perform some processing before the zoom is done
    void onMouseWheel(QWheelEvent *event) noexcept;

    void onDataCacheVariableUpdated();
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
