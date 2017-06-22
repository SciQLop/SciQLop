#ifndef SCIQLOP_VISUALIZATIONTABWIDGET_H
#define SCIQLOP_VISUALIZATIONTABWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <Common/spimpl.h>

#include <QWidget>

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

    /// Create a zone using a Variable
    VisualizationZoneWidget *createZone();

    /// Remove a zone
    void removeZone(VisualizationZoneWidget *zone);

    // IVisualizationWidget interface
    void accept(IVisualizationWidget *visitor) override;
    void close() override;
    QString name() const override;

private:
    Ui::VisualizationTabWidget *ui;

    class VisualizationTabWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationTabWidgetPrivate> impl;
};

#endif // SCIQLOP_VISUALIZATIONTABWIDGET_H
