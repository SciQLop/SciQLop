#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationGraphWidget)

class QCPRange;
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

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    void close() override;
    QString name() const override;

    void updateDisplay(std::shared_ptr<Variable> variable);


private:
    Ui::VisualizationGraphWidget *ui;

    class VisualizationGraphWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationGraphWidgetPrivate> impl;

private slots:

    void onRangeChanged(const QCPRange &t1, const QCPRange &t2);

    /// Slot called when a mouse wheel was made, to perform some processing before the zoom is done
    void onMouseWheel(QWheelEvent *event) noexcept;

    void onDataCacheVariableUpdated();
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
