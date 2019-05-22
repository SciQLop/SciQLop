#include "toolbar.h"
#include <QIcon>
#include <QMenu>
#include <QStringLiteral>
#include <tuple>

using InteractionMode = SqpApplication::PlotsInteractionMode;
using CursorMode = SqpApplication::PlotsCursorMode;

ToolBar::ToolBar(QWidget* parent)
{
#define mk_tuple std::make_tuple

    for (auto [action, icon, text, checkable] :
        { mk_tuple(&this->timeRange, ":/icones/Simple_icon_time.svg", "Set time range", false),
            mk_tuple(&this->pointerMode, ":/icones/pointer.png", "Move", true),
            mk_tuple(&this->zoomMode, ":/icones/zoom.png", "Zoom", true),
            mk_tuple(&this->organizationMode, ":/icones/drag.png", "Organize", true),
            mk_tuple(&this->zonesMode, ":/icones/rectangle.png", "Zones", true),
            mk_tuple(&this->cursorsActn, ":/icones/cursor.png", "Cursors", false),
            mk_tuple(&this->cataloguesActn, ":/icones/catalogue.png", "Catalogues", false) })
    {
        *action = new QAction(QIcon(icon), text, this);
        (*action)->setCheckable(checkable);
        this->addAction(*action);
    }
    connect(this->cataloguesActn, &QAction::triggered, this, &ToolBar::showCataloguesBrowser);
    this->pointerMode->setChecked(true);
    {
        this->cursorsActn->setMenu(new QMenu());
        auto menu = this->cursorsActn->menu();
        auto group = new QActionGroup { this };
        group->setExclusive(true);
        for (auto [icon, text, mode, checked] :
            { mk_tuple("", "No Cursor", CursorMode::NoCursor, true),
                mk_tuple("", "Vertical Cursor", CursorMode::Vertical, false),
                mk_tuple("", "Horizontal Cursor", CursorMode::Horizontal, false),
                mk_tuple("", "Cross Cursor", CursorMode::Cross, false) })
        {
            auto action = menu->addAction(text);
            group->addAction(action);
            action->setCheckable(true);
            action->setChecked(checked);
            connect(action, &QAction::triggered,
                [this, mode = mode]() { emit this->setPlotsCursorMode(mode); });
        }
    }

    for (auto [actn, mode] : { mk_tuple(this->pointerMode, InteractionMode::None),
             mk_tuple(this->zoomMode, InteractionMode::ZoomBox),
             mk_tuple(this->organizationMode, InteractionMode::DragAndDrop),
             mk_tuple(this->zonesMode, InteractionMode::SelectionZones) })
    {
        connect(actn, &QAction::triggered,
            [this, mode = mode]() { emit this->setPlotsInteractionMode(mode); });
    }

    auto cursorModeActionGroup = new QActionGroup { this };
    cursorModeActionGroup->setExclusive(true);
    for (auto actn : { this->pointerMode, this->organizationMode, this->zoomMode, this->zonesMode })
    {
        cursorModeActionGroup->addAction(actn);
    }

    this->timeWidget = new TimeWidgetAction();
    this->timeRange->setMenu(new QMenu());
    this->timeRange->menu()->addAction(this->timeWidget);
}
