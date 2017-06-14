#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QWidget>

#include <memory>

#include <Common/spimpl.h>

class Variable;

namespace Ui {
class VisualizationGraphWidget;
} // namespace Ui

class VisualizationGraphWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationGraphWidget(QWidget *parent = 0);
    virtual ~VisualizationGraphWidget();

    void addVariable(std::shared_ptr<Variable> variable);

    // IVisualizationWidget interface
    void accept(IVisualizationWidget *visitor) override;
    void close() override;
    QString name() const;

private:
    Ui::VisualizationGraphWidget *ui;

    class VisualizationGraphWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationGraphWidgetPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
