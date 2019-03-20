#ifndef SCIQLOP_VISUALIZATIONWIDGET_H
#define SCIQLOP_VISUALIZATIONWIDGET_H

#include "Visualization/IVisualizationWidget.h"
#include <Data/DateTimeRange.h>

#include <QLoggingCategory>
#include <QWidget>

#include <Common/spimpl.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationWidget)

class QMenu;
class Variable2;
class VisualizationTabWidget;
class VisualizationSelectionZoneManager;

namespace Ui
{
class VisualizationWidget;
} // namespace Ui

class VisualizationWidget : public QWidget, public IVisualizationWidget
{
    Q_OBJECT

public:
    explicit VisualizationWidget(QWidget* parent = 0);
    virtual ~VisualizationWidget();

    /// Returns the class which manage the selection of selection zone across the visualization
    VisualizationSelectionZoneManager& selectionZoneManager() const;

    VisualizationTabWidget* currentTabWidget() const;

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor* visitor) override;
    bool canDrop(Variable2& variable) const override;
    bool contains(Variable2& variable) const override;
    QString name() const override;

public slots:
    /**
     * Attaches to a menu the menu relative to the visualization of variables
     * @param menu the parent menu of the generated menu
     * @param variables the variables for which to generate the menu
     */
    void attachVariableMenu(
        QMenu* menu, const QVector<std::shared_ptr<Variable2>>& variables) noexcept;

    /// Slot called when a variable is about to be deleted from SciQlop
    void onVariableAboutToBeDeleted(std::shared_ptr<Variable2> variable) noexcept;

    void onRangeChanged(std::shared_ptr<Variable2> variable, const DateTimeRange& range) noexcept;

protected:
    void closeEvent(QCloseEvent* event) override;

private:
    Ui::VisualizationWidget* ui;

    class VisualizationWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationWidgetPrivate> impl;
};

#endif // VISUALIZATIONWIDGET_H
