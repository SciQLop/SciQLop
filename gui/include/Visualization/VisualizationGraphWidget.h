#ifndef SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
#define SCIQLOP_VISUALIZATIONGRAPHWIDGET_H

#include "Visualization/IVisualizationWidget.h"
#include "Visualization/VisualizationDragWidget.h"

#include <QLoggingCategory>
#include <QUuid>
#include <QWidget>
#include <QEnterEvent>

#include <memory>

#include <Common/spimpl.h>

#include <Data/DateTimeRange.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_VisualizationGraphWidget)

class QCPRange;
class QCustomPlot;
class Variable2;
class VisualizationWidget;
class VisualizationZoneWidget;
class VisualizationSelectionZoneItem;

#if QT_VERSION < QT_VERSION_CHECK(6, 0, 0)
    #define AnyEvent_t QEvent
#else
    #define AnyEvent_t QEnterEvent
#endif

namespace Ui
{
class VisualizationGraphWidget;
} // namespace Ui

/// Defines options that can be associated with the graph
enum GraphFlag
{
    DisableAll = 0x0, ///< Disables acquisition and synchronization
    EnableAcquisition = 0x1, ///< When this flag is set, the change of the graph's range leads to
                             /// the acquisition of data
    EnableSynchronization = 0x2, ///< When this flag is set, the change of the graph's range causes
                                 /// the call to the synchronization of the graphs contained in the
    /// same zone of this graph
    EnableAll = ~DisableAll ///< Enables acquisition and synchronization
};

Q_DECLARE_FLAGS(GraphFlags, GraphFlag)
Q_DECLARE_OPERATORS_FOR_FLAGS(GraphFlags)

class VisualizationGraphWidget : public VisualizationDragWidget, public IVisualizationWidget
{
    Q_OBJECT

    friend class QCustomPlotSynchronizer;
    friend class VisualizationGraphRenderingDelegate;

public:
    explicit VisualizationGraphWidget(const QString& name = {}, QWidget* parent = 0);
    virtual ~VisualizationGraphWidget();

    /// Returns the VisualizationZoneWidget which contains the graph or nullptr
    VisualizationZoneWidget* parentZoneWidget() const noexcept;

    /// Returns the main VisualizationWidget which contains the graph or nullptr
    VisualizationWidget* parentVisualizationWidget() const;

    /// Sets graph options
    void setFlags(GraphFlags flags);

    void addVariable(std::shared_ptr<Variable2> variable, DateTimeRange range);

    /// Removes a variable from the graph
    void removeVariable(std::shared_ptr<Variable2> variable) noexcept;

    /// Returns the list of all variables used in the graph
    std::vector<std::shared_ptr<Variable2>> variables() const;

    /// Sets the y-axis range based on the data of a variable
    void setYRange(std::shared_ptr<Variable2> variable);
    DateTimeRange graphRange() const noexcept;
    void setGraphRange(const DateTimeRange& range, bool updateVar = false, bool forward = false);
    void setAutoRangeOnVariableInitialization(bool value);

    // Zones
    /// Returns the ranges of all the selection zones on the graph
    QVector<DateTimeRange> selectionZoneRanges() const;
    /// Adds new selection zones in the graph
    void addSelectionZones(const QVector<DateTimeRange>& ranges);
    /// Adds a new selection zone in the graph
    VisualizationSelectionZoneItem* addSelectionZone(
        const QString& name, const DateTimeRange& range);
    /// Removes the specified selection zone
    void removeSelectionZone(VisualizationSelectionZoneItem* selectionZone);

    /// Undo the last zoom  done with a zoom box
    void undoZoom();

    void zoom(double factor, int center, Qt::Orientation orientation, bool forward = true);
    void move(double factor, Qt::Orientation orientation, bool forward = true);
    void move(double dx, double dy, bool forward = true);
    void transform(const DateTimeRangeTransformation& tranformation, bool forward = true);

    void toggle_y_log_scale();

    // IVisualizationWidget interface
    void accept(IVisualizationWidgetVisitor* visitor) override;
    bool canDrop(Variable2& variable) const override;
    bool contains(Variable2& variable) const override;
    QString name() const override;

    // VisualisationDragWidget
    QMimeData* mimeData(const QPoint& position) const override;
    QPixmap customDragPixmap(const QPoint& dragPosition) override;
    bool isDragAllowed() const override;
    void highlightForMerge(bool highlighted) override;

    // Cursors
    /// Adds or moves the vertical cursor at the specified value on the x-axis
    void addVerticalCursor(double time);
    /// Adds or moves the vertical cursor at the specified value on the x-axis
    void addVerticalCursorAtViewportPosition(double position);
    void removeVerticalCursor();
    /// Adds or moves the vertical cursor at the specified value on the y-axis
    void addHorizontalCursor(double value);
    /// Adds or moves the vertical cursor at the specified value on the y-axis
    void addHorizontalCursorAtViewportPosition(double position);
    void removeHorizontalCursor();

signals:
    void synchronize(const DateTimeRange& range, const DateTimeRange& oldRange);
    void changeRange(const std::shared_ptr<Variable2>& variable, const DateTimeRange& range);

    /// Signal emitted when the variable is about to be removed from the graph
    void variableAboutToBeRemoved(std::shared_ptr<Variable2> var);
    /// Signal emitted when the variable has been added to the graph
    void variableAdded(std::shared_ptr<Variable2> var);


    void zoom_sig(double factor, int center, Qt::Orientation orientation, bool forward = true);
    void move_sig(double factor, Qt::Orientation orientation, bool forward = true);
    void move_sig(double dx, double dy, bool forward = true);
    void transform_sig(const DateTimeRangeTransformation& tranformation, bool forward = true);
    void setrange_sig(const DateTimeRange& range, bool updateVar = false, bool forward = true);

protected:
    void closeEvent(QCloseEvent* event) override;
    void enterEvent(AnyEvent_t* event) override;
    void leaveEvent(QEvent* event) override;
    void wheelEvent(QWheelEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseDoubleClickEvent(QMouseEvent* event) override;
    void keyReleaseEvent(QKeyEvent* event) override;
    void keyPressEvent(QKeyEvent* event) override;

    QCustomPlot& plot() const noexcept;

private:
    Ui::VisualizationGraphWidget* ui;

    class VisualizationGraphWidgetPrivate;
    spimpl::unique_impl_ptr<VisualizationGraphWidgetPrivate> impl;

private slots:
    /// Slot called when right clicking on the graph (displays a menu)
    void onGraphMenuRequested(const QPoint& pos) noexcept;

    /// Rescale the X axe to range parameter
    // void onRangeChanged(const QCPRange &newRange, const QCPRange &oldRange);

    /// Slot called when a mouse double click was made
    void onMouseDoubleClick(QMouseEvent* event) noexcept;
    /// Slot called when a mouse move was made
    void onMouseMove(QMouseEvent* event) noexcept;
    /// Slot called when a mouse wheel was made, to perform some processing before the zoom is done
    void onMouseWheel(QWheelEvent* event) noexcept;
    /// Slot called when a mouse press was made, to activate the calibration of a graph
    void onMousePress(QMouseEvent* event) noexcept;
    /// Slot called when a mouse release was made, to deactivate the calibration of a graph
    void onMouseRelease(QMouseEvent* event) noexcept;

    void onDataCacheVariableUpdated();

    void onUpdateVarDisplaying(std::shared_ptr<Variable2> variable, const DateTimeRange& range);

    void variableUpdated(QUuid id);
    void variableDeleted(const std::shared_ptr<Variable2>&);
};

#endif // SCIQLOP_VISUALIZATIONGRAPHWIDGET_H
