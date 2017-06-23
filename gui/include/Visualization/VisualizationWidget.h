#ifndef SCIQLOP_VISUALIZATIONWIDGET_H
#define SCIQLOP_VISUALIZATIONWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <QLoggingCategory>
#include <QWidget>

class Variable;
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
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    void close() override;
    QString name() const override;

public slots:
    /**
     * Displays a variable in a new graph of a new zone of the current tab
     * @param variable the variable to display
     * @todo this is a temporary method that will be replaced by own actions for each type of
     * visualization widget
     */
    void displayVariable(std::shared_ptr<Variable> variable) noexcept;

private:
    Ui::VisualizationWidget *ui;
};

#endif // VISUALIZATIONWIDGET_H
