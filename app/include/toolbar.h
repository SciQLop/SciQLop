#ifndef TOOLBAR_H
#define TOOLBAR_H

#include <Data/DateTimeRange.h>
#include <QAction>
#include <QActionGroup>
#include <QObject>
#include <QToolBar>
#include <QWidget>
#include <TimeWidget/TimeWidget.h>

// @TODO remove this, shouldn't need to include SqpApplication to get PlotsInteractionMode
#include <SqpApplication.h>

class ToolBar : public QToolBar
{
    Q_OBJECT
public:
    explicit ToolBar(QWidget* parent = nullptr);

    QAction* timeRange;
    QAction* pointerMode;
    QAction* zoomMode;
    QAction* organizationMode;
    QAction* zonesMode;
    QAction* cursorsActn;
    QAction* cataloguesActn;

    TimeWidgetAction* timeWidget;
signals:
    void setPlotsInteractionMode(SqpApplication::PlotsInteractionMode);
    void setPlotsCursorMode(SqpApplication::PlotsCursorMode);
    void timeUpdated(DateTimeRange time);
    void showCataloguesBrowser();
};

#endif // TOOLBAR_H
