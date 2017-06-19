#ifndef SCIQLOP_VISUALIZATIONWIDGET_H
#define SCIQLOP_VISUALIZATIONWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QLoggingCategory>
#include <QWidget>

class VisualizationTabWidget;

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationWidget)

namespace Ui {
class VisualizationWidget;
} // namespace Ui

class VisualizationWidget : public QWidget, public IVisualizationWidget {
    Q_OBJECT

public:
    explicit VisualizationWidget(QWidget *parent = 0);
    virtual ~VisualizationWidget();

    /// Add a zone widget
    virtual void addTab(VisualizationTabWidget *tabWidget);

    /// Create a tab using a Variable
    VisualizationTabWidget *createTab();

    /// Remove a tab
    void removeTab(VisualizationTabWidget *tab);

    // IVisualizationWidget interface
    void accept(IVisualizationWidget *visitor) override;
    void close() override;
    QString name() const;

private:
    Ui::VisualizationWidget *ui;
};

#endif // VISUALIZATIONWIDGET_H
