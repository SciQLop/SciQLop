#ifndef SCIQLOP_VISUALIZATIONTABWIDGET_H
#define SCIQLOP_VISUALIZATIONTABWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QWidget>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationTabWidget)

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

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

private:
    /// @return the layout of tab in which zones are added
    QLayout &tabLayout() const noexcept;

    Ui::VisualizationTabWidget *ui;

    class VisualizationTabWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationTabWidgetPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONTABWIDGET_H
