/*------------------------------------------------------------------------------
-- This file is a part of the SciQLop Software
-- Copyright (C) 2017, Plasma Physics Laboratory - CNRS
--
-- This program is free software; you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation; either version 2 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program; if not, write to the Free Software
-- Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
-------------------------------------------------------------------------------*/
/*-- Author : Alexis Jeandet
-- Mail : alexis.jeandet@member.fsf.org
----------------------------------------------------------------------------*/
#include "MainWindow.h"
#include "ui_MainWindow.h"

#include <Catalogue/CatalogueController.h>
#include <Catalogue/CatalogueExplorer.h>
#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceWidget.h>
#include <Settings/SqpSettingsDialog.h>
#include <Settings/SqpSettingsGeneralWidget.h>
#include <SidePane/SqpSidePane.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <TimeWidget/TimeWidget.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>
#include <Visualization/VisualizationController.h>

#include <QAction>
#include <QCloseEvent>
#include <QDate>
#include <QDir>
#include <QFileDialog>
#include <QMessageBox>
#include <QToolBar>
#include <QToolButton>
#include <memory.h>

#include "iostream"

Q_LOGGING_CATEGORY(LOG_MainWindow, "MainWindow")

namespace {
const auto LEFTMAININSPECTORWIDGETSPLITTERINDEX = 0;
const auto LEFTINSPECTORSIDEPANESPLITTERINDEX = 1;
const auto VIEWPLITTERINDEX = 2;
const auto RIGHTINSPECTORSIDEPANESPLITTERINDEX = 3;
const auto RIGHTMAININSPECTORWIDGETSPLITTERINDEX = 4;
}

class MainWindow::MainWindowPrivate {
public:
    explicit MainWindowPrivate(MainWindow *mainWindow)
            : m_LastOpenLeftInspectorSize{},
              m_LastOpenRightInspectorSize{},
              m_GeneralSettingsWidget{new SqpSettingsGeneralWidget{mainWindow}},
              m_SettingsDialog{new SqpSettingsDialog{mainWindow}},
              m_CatalogExplorer{new CatalogueExplorer{mainWindow}}
    {
    }

    QSize m_LastOpenLeftInspectorSize;
    QSize m_LastOpenRightInspectorSize;
    /// General settings widget. MainWindow has the ownership
    SqpSettingsGeneralWidget *m_GeneralSettingsWidget;
    /// Settings dialog. MainWindow has the ownership
    SqpSettingsDialog *m_SettingsDialog;
    /// Catalogue dialog. MainWindow has the ownership
    CatalogueExplorer *m_CatalogExplorer;

    bool checkDataToSave(QWidget *parentWidget);
};

MainWindow::MainWindow(QWidget *parent)
        : QMainWindow{parent},
          m_Ui{new Ui::MainWindow},
          impl{spimpl::make_unique_impl<MainWindowPrivate>(this)}
{
    m_Ui->setupUi(this);

    m_Ui->splitter->setCollapsible(LEFTINSPECTORSIDEPANESPLITTERINDEX, false);
    m_Ui->splitter->setCollapsible(RIGHTINSPECTORSIDEPANESPLITTERINDEX, false);

    impl->m_CatalogExplorer->setVisualizationWidget(m_Ui->view);


    auto leftSidePane = m_Ui->leftInspectorSidePane->sidePane();
    auto openLeftInspectorAction = new QAction{QIcon{
                                                   ":/icones/previous.png",
                                               },
                                               tr("Show/hide the left inspector"), this};


    auto spacerLeftTop = new QWidget{};
    spacerLeftTop->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    auto spacerLeftBottom = new QWidget{};
    spacerLeftBottom->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    leftSidePane->addWidget(spacerLeftTop);
    leftSidePane->addAction(openLeftInspectorAction);
    leftSidePane->addWidget(spacerLeftBottom);


    auto rightSidePane = m_Ui->rightInspectorSidePane->sidePane();
    auto openRightInspectorAction = new QAction{QIcon{
                                                    ":/icones/next.png",
                                                },
                                                tr("Show/hide the right inspector"), this};

    auto spacerRightTop = new QWidget{};
    spacerRightTop->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    auto spacerRightBottom = new QWidget{};
    spacerRightBottom->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    rightSidePane->addWidget(spacerRightTop);
    rightSidePane->addAction(openRightInspectorAction);
    rightSidePane->addWidget(spacerRightBottom);

    openLeftInspectorAction->setCheckable(true);
    openRightInspectorAction->setCheckable(true);

    auto openInspector = [this](bool checked, bool right, auto action) {

        action->setIcon(QIcon{(checked ^ right) ? ":/icones/next.png" : ":/icones/previous.png"});

        auto &lastInspectorSize
            = right ? impl->m_LastOpenRightInspectorSize : impl->m_LastOpenLeftInspectorSize;

        auto nextInspectorSize = right ? m_Ui->rightMainInspectorWidget->size()
                                       : m_Ui->leftMainInspectorWidget->size();

        // Update of the last opened geometry
        if (checked) {
            lastInspectorSize = nextInspectorSize;
        }

        auto startSize = lastInspectorSize;
        auto endSize = startSize;
        endSize.setWidth(0);

        auto splitterInspectorIndex
            = right ? RIGHTMAININSPECTORWIDGETSPLITTERINDEX : LEFTMAININSPECTORWIDGETSPLITTERINDEX;

        auto currentSizes = m_Ui->splitter->sizes();
        if (checked) {
            // adjust sizes individually here, e.g.
            currentSizes[splitterInspectorIndex] -= lastInspectorSize.width();
            currentSizes[VIEWPLITTERINDEX] += lastInspectorSize.width();
            m_Ui->splitter->setSizes(currentSizes);
        }
        else {
            // adjust sizes individually here, e.g.
            currentSizes[splitterInspectorIndex] += lastInspectorSize.width();
            currentSizes[VIEWPLITTERINDEX] -= lastInspectorSize.width();
            m_Ui->splitter->setSizes(currentSizes);
        }

    };


    connect(openLeftInspectorAction, &QAction::triggered,
            [openInspector, openLeftInspectorAction](bool checked) {
                openInspector(checked, false, openLeftInspectorAction);
            });
    connect(openRightInspectorAction, &QAction::triggered,
            [openInspector, openRightInspectorAction](bool checked) {
                openInspector(checked, true, openRightInspectorAction);
            });

    // //////////////// //
    // Menu and Toolbar //
    // //////////////// //
    this->menuBar()->addAction(tr("File"));
    auto toolsMenu = this->menuBar()->addMenu(tr("Tools"));
    toolsMenu->addAction(tr("Settings..."), [this]() {
        // Loads settings
        impl->m_SettingsDialog->loadSettings();

        // Open settings dialog and save settings if the dialog is accepted
        if (impl->m_SettingsDialog->exec() == QDialog::Accepted) {
            impl->m_SettingsDialog->saveSettings();
        }

    });

    auto mainToolBar = this->addToolBar(QStringLiteral("MainToolBar"));

    auto timeWidget = new TimeWidget{};
    mainToolBar->addWidget(timeWidget);

    // Interaction modes
    auto actionPointerMode = new QAction{QIcon(":/icones/pointer.png"), "Move", this};
    actionPointerMode->setCheckable(true);
    actionPointerMode->setChecked(sqpApp->plotsInteractionMode()
                                  == SqpApplication::PlotsInteractionMode::None);
    connect(actionPointerMode, &QAction::triggered,
            []() { sqpApp->setPlotsInteractionMode(SqpApplication::PlotsInteractionMode::None); });

    auto actionZoomMode = new QAction{QIcon(":/icones/zoom.png"), "Zoom", this};
    actionZoomMode->setCheckable(true);
    actionZoomMode->setChecked(sqpApp->plotsInteractionMode()
                               == SqpApplication::PlotsInteractionMode::ZoomBox);
    connect(actionZoomMode, &QAction::triggered, []() {
        sqpApp->setPlotsInteractionMode(SqpApplication::PlotsInteractionMode::ZoomBox);
    });

    auto actionOrganisationMode = new QAction{QIcon(":/icones/drag.png"), "Organize", this};
    actionOrganisationMode->setCheckable(true);
    actionOrganisationMode->setChecked(sqpApp->plotsInteractionMode()
                                       == SqpApplication::PlotsInteractionMode::DragAndDrop);
    connect(actionOrganisationMode, &QAction::triggered, []() {
        sqpApp->setPlotsInteractionMode(SqpApplication::PlotsInteractionMode::DragAndDrop);
    });

    auto actionZonesMode = new QAction{QIcon(":/icones/rectangle.png"), "Zones", this};
    actionZonesMode->setCheckable(true);
    actionZonesMode->setChecked(sqpApp->plotsInteractionMode()
                                == SqpApplication::PlotsInteractionMode::SelectionZones);
    connect(actionZonesMode, &QAction::triggered, []() {
        sqpApp->setPlotsInteractionMode(SqpApplication::PlotsInteractionMode::SelectionZones);
    });

    auto modeActionGroup = new QActionGroup{this};
    modeActionGroup->addAction(actionZoomMode);
    modeActionGroup->addAction(actionZonesMode);
    modeActionGroup->addAction(actionOrganisationMode);
    modeActionGroup->addAction(actionPointerMode);
    modeActionGroup->setExclusive(true);

    mainToolBar->addSeparator();
    mainToolBar->addAction(actionPointerMode);
    mainToolBar->addAction(actionZoomMode);
    mainToolBar->addAction(actionOrganisationMode);
    mainToolBar->addAction(actionZonesMode);
    mainToolBar->addSeparator();

    // Cursors
    auto btnCursor = new QToolButton{this};
    btnCursor->setIcon(QIcon(":/icones/cursor.png"));
    btnCursor->setText("Cursor");
    btnCursor->setToolTip("Cursor");
    btnCursor->setPopupMode(QToolButton::InstantPopup);
    auto cursorMenu = new QMenu("CursorMenu", this);
    btnCursor->setMenu(cursorMenu);

    auto noCursorAction = cursorMenu->addAction("No Cursor");
    noCursorAction->setCheckable(true);
    noCursorAction->setChecked(sqpApp->plotsCursorMode()
                               == SqpApplication::PlotsCursorMode::NoCursor);
    connect(noCursorAction, &QAction::triggered,
            []() { sqpApp->setPlotsCursorMode(SqpApplication::PlotsCursorMode::NoCursor); });

    cursorMenu->addSeparator();
    auto verticalCursorAction = cursorMenu->addAction("Vertical Cursor");
    verticalCursorAction->setCheckable(true);
    verticalCursorAction->setChecked(sqpApp->plotsCursorMode()
                                     == SqpApplication::PlotsCursorMode::Vertical);
    connect(verticalCursorAction, &QAction::triggered,
            []() { sqpApp->setPlotsCursorMode(SqpApplication::PlotsCursorMode::Vertical); });

    auto temporalCursorAction = cursorMenu->addAction("Temporal Cursor");
    temporalCursorAction->setCheckable(true);
    temporalCursorAction->setChecked(sqpApp->plotsCursorMode()
                                     == SqpApplication::PlotsCursorMode::Temporal);
    connect(temporalCursorAction, &QAction::triggered,
            []() { sqpApp->setPlotsCursorMode(SqpApplication::PlotsCursorMode::Temporal); });

    auto horizontalCursorAction = cursorMenu->addAction("Horizontal Cursor");
    horizontalCursorAction->setCheckable(true);
    horizontalCursorAction->setChecked(sqpApp->plotsCursorMode()
                                       == SqpApplication::PlotsCursorMode::Horizontal);
    connect(horizontalCursorAction, &QAction::triggered,
            []() { sqpApp->setPlotsCursorMode(SqpApplication::PlotsCursorMode::Horizontal); });

    auto crossCursorAction = cursorMenu->addAction("Cross Cursor");
    crossCursorAction->setCheckable(true);
    crossCursorAction->setChecked(sqpApp->plotsCursorMode()
                                  == SqpApplication::PlotsCursorMode::Cross);
    connect(crossCursorAction, &QAction::triggered,
            []() { sqpApp->setPlotsCursorMode(SqpApplication::PlotsCursorMode::Cross); });

    mainToolBar->addWidget(btnCursor);

    auto cursorModeActionGroup = new QActionGroup{this};
    cursorModeActionGroup->setExclusive(true);
    cursorModeActionGroup->addAction(noCursorAction);
    cursorModeActionGroup->addAction(verticalCursorAction);
    cursorModeActionGroup->addAction(temporalCursorAction);
    cursorModeActionGroup->addAction(horizontalCursorAction);
    cursorModeActionGroup->addAction(crossCursorAction);

    // Catalog
    mainToolBar->addSeparator();
    mainToolBar->addAction(QIcon(":/icones/catalogue.png"), "Catalogues",
                           [this]() { impl->m_CatalogExplorer->show(); });

    // //////// //
    // Settings //
    // //////// //

    // Registers "general settings" widget to the settings dialog
    impl->m_SettingsDialog->registerWidget(QStringLiteral("General"),
                                           impl->m_GeneralSettingsWidget);

    // /////////// //
    // Connections //
    // /////////// //

    // Controllers / controllers connections
//    connect(&sqpApp->timeController(), SIGNAL(timeUpdated(DateTimeRange)), &sqpApp->variableController(),
//            SLOT(onDateTimeOnSelection(DateTimeRange)));

    // Widgets / controllers connections

    // DataSource
    connect(&sqpApp->dataSourceController(), SIGNAL(dataSourceItemSet(DataSourceItem *)),
            m_Ui->dataSourceWidget, SLOT(addDataSource(DataSourceItem *)));

    // Time
    connect(timeWidget, SIGNAL(timeUpdated(DateTimeRange)), &sqpApp->timeController(),
            SLOT(onTimeToUpdate(DateTimeRange)));

    // Visualization
    connect(&sqpApp->visualizationController(),
            SIGNAL(variableAboutToBeDeleted(std::shared_ptr<Variable>)), m_Ui->view,
            SLOT(onVariableAboutToBeDeleted(std::shared_ptr<Variable>)));

    connect(&sqpApp->visualizationController(),
            SIGNAL(rangeChanged(std::shared_ptr<Variable>, const DateTimeRange &)), m_Ui->view,
            SLOT(onRangeChanged(std::shared_ptr<Variable>, const DateTimeRange &)));

    // Widgets / widgets connections

    // For the following connections, we use DirectConnection to allow each widget that can
    // potentially attach a menu to the variable's menu to do so before this menu is displayed.
    // The order of connections is also important, since it determines the order in which each
    // widget will attach its menu
    connect(
        m_Ui->variableInspectorWidget,
        SIGNAL(tableMenuAboutToBeDisplayed(QMenu *, const QVector<std::shared_ptr<Variable> > &)),
        m_Ui->view, SLOT(attachVariableMenu(QMenu *, const QVector<std::shared_ptr<Variable> > &)),
        Qt::DirectConnection);
}

MainWindow::~MainWindow()
{
}

void MainWindow::changeEvent(QEvent *e)
{
    QMainWindow::changeEvent(e);
    switch (e->type()) {
        case QEvent::LanguageChange:
            m_Ui->retranslateUi(this);
            break;
        default:
            break;
    }
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    if (!impl->checkDataToSave(this)) {
        event->ignore();
    }
    else {
        event->accept();
    }
}

bool MainWindow::MainWindowPrivate::checkDataToSave(QWidget *parentWidget)
{
    auto hasChanges = sqpApp->catalogueController().hasChanges();
    if (hasChanges) {
        // There are some unsaved changes
        switch (QMessageBox::question(
            parentWidget, tr("Save changes"),
            tr("The catalogue controller has unsaved changes.\nDo you want to save them ?"),
            QMessageBox::SaveAll | QMessageBox::Discard | QMessageBox::Cancel,
            QMessageBox::SaveAll)) {
            case QMessageBox::SaveAll:
                sqpApp->catalogueController().saveAll();
                break;
            case QMessageBox::Discard:
                break;
            case QMessageBox::Cancel:
            default:
                return false;
        }
    }

    return true;
}
