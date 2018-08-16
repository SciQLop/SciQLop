#ifndef SCIQLOP_VISUALIZATIONTABWIDGET_H
#define SCIQLOP_VISUALIZATIONTABWIDGET_H

#include "Visualization/IVisualizationWidget.h"

#include <Common/spimpl.h>

#include <QLoggingCategory>
#include <QMimeData>
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

    /// Adds a zone widget
    void addZone(VisualizationZoneWidget *zoneWidget);

    /// Inserts a zone widget at the specified position
    void insertZone(int index, VisualizationZoneWidget *zoneWidget);

    /// Returns the list of zone widget names in the order they are displayed
    QStringList availableZoneWidgets() const;

    /// Returns the zone with the specified name.
    /// If multiple zone with the same name exist, the first one is returned.
    VisualizationZoneWidget *getZoneWithName(const QString &zoneName);

    /**
     * Creates a zone using a variable. The variable will be displayed in a new graph of the new
     * zone. The zone is added at the end.
     * @param variable the variable for which to create the zone
     * @return the pointer to the created zone
     */
    VisualizationZoneWidget *createZone(std::shared_ptr<Variable> variable);

    /**
     * Creates a zone using a list of variables. The variables will be displayed in a new graph of
     * the new zone. The zone is inserted at the specified index.
     * @param variables the variables for which to create the zone
     * @param index The index where the zone should be inserted in the layout
     * @return the pointer to the created zone
     */
    VisualizationZoneWidget *createZone(const std::vector<std::shared_ptr<Variable> > &variables,
                                        int index);

    /**
     * Creates a zone which is empty (no variables). The zone is inserted at the specified index.
     * @param index The index where the zone should be inserted in the layout
     * @return the pointer to the created zone
     */
    VisualizationZoneWidget *createEmptyZone(int index);

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor *visitor) override;
    bool canDrop(const Variable &variable) const override;
    bool contains(const Variable &variable) const override;
    QString name() const override;

protected:
    void closeEvent(QCloseEvent *event) override;

private:
    /// @return the layout of tab in which zones are added
    QLayout &tabLayout() const noexcept;

    Ui::VisualizationTabWidget *ui;

    class VisualizationTabWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationTabWidgetPrivate> impl;

private slots:
    void dropMimeData(int index, const QMimeData *mimeData);
};

#endif // SCIQLOP_VISUALIZATIONTABWIDGET_H
