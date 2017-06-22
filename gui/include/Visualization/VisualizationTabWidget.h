#ifndef SCIQLOP_VISUALIZATIONTABWIDGET_H
#define SCIQLOP_VISUALIZATIONTABWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <Common/spimpl.h>

#include <QWidget>

class Variable;
class VisualizationZoneWidget;

namespace Ui {
class VisualizationTabWidget;
} // namespace Ui

class VisualizationTabWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationTabWidget(const QString &name = {}, QWidget *parent = 0);
    virtual ~VisualizationTabWidget();

    /// Add a zone widget
    void addZone(VisualizationZoneWidget *zoneWidget);

    /**
     * Creates a zone using a variable. The variable will be displayed in a new graph of the new
     * zone.
     * @param variable the variable for which to create the zone
     * @return the pointer to the created zone
     */
    VisualizationZoneWidget *createZone(std::shared_ptr<Variable> variable);

    /// Remove a zone
    void removeZone(VisualizationZoneWidget *zone);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    void close() override;
    QString name() const override;

private:
    Ui::VisualizationTabWidget *ui;

    class VisualizationTabWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationTabWidgetPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONTABWIDGET_H
