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
#include <Catalogue2/browser.h>
#include <DataSource/DataSourceItem.h>
#include <DataSource/DataSourceWidget.h>
#include <Settings/SqpSettingsDialog.h>
#include <Settings/SqpSettingsGeneralWidget.h>
#include <SidePane/SqpSidePane.h>
#include <SqpApplication.h>
#include <Time/TimeController.h>
#include <TimeWidget/TimeWidget.h>

#include "toolbar.h"

#include <QAction>
#include <QCloseEvent>
#include <QDate>
#include <QDir>
#include <QFileDialog>
#include <QMessageBox>
#include <QToolBar>
#include <QToolButton>
#include <memory.h>


Q_LOGGING_CATEGORY(LOG_MainWindow, "MainWindow")

class MainWindow::MainWindowPrivate
{
public:
    explicit MainWindowPrivate(MainWindow* mainWindow)
            : m_GeneralSettingsWidget { new SqpSettingsGeneralWidget { mainWindow } }
            , m_SettingsDialog { new SqpSettingsDialog { mainWindow } }
            , m_CatalogExplorer { new CataloguesBrowser { mainWindow } }
    {
    }

    /// General settings widget. MainWindow has the ownership
    SqpSettingsGeneralWidget* m_GeneralSettingsWidget;
    /// Settings dialog. MainWindow has the ownership
    SqpSettingsDialog* m_SettingsDialog;
    /// Catalogue dialog. MainWindow has the ownership
    CataloguesBrowser* m_CatalogExplorer;

    bool checkDataToSave(QWidget* parentWidget);
};

MainWindow::MainWindow(QWidget* parent)
        : QMainWindow { parent }
        , m_Ui { new Ui::MainWindow }
        , impl { spimpl::make_unique_impl<MainWindowPrivate>(this) }
{
    m_Ui->setupUi(this);
    setWindowTitle(QString("SciQLop v%1").arg(SCIQLOP_VERSION));

    // //////////////// //
    // Menu and Toolbar //
    // //////////////// //
    this->menuBar()->addAction(tr("File"));
    auto toolsMenu = this->menuBar()->addMenu(tr("Tools"));
    toolsMenu->addAction(tr("Settings..."), [this]() {
        // Loads settings
        impl->m_SettingsDialog->loadSettings();

        // Open settings dialog and save settings if the dialog is accepted
        if (impl->m_SettingsDialog->exec() == QDialog::Accepted)
        {
            impl->m_SettingsDialog->saveSettings();
        }
    });
    auto mainToolBar = new ToolBar(this);
    this->addToolBar(mainToolBar);
    connect(mainToolBar, &ToolBar::setPlotsInteractionMode, sqpApp,
        &SqpApplication::setPlotsInteractionMode);
    connect(mainToolBar, &ToolBar::setPlotsCursorMode, sqpApp, &SqpApplication::setPlotsCursorMode);
    connect(mainToolBar, &ToolBar::showCataloguesBrowser,
        [this]() { impl->m_CatalogExplorer->show(); });

    // //////// //
    // Settings //
    // //////// //

    // Registers "general settings" widget to the settings dialog
    impl->m_SettingsDialog->registerWidget(
        QStringLiteral("General"), impl->m_GeneralSettingsWidget);

    // /////////// //
    // Connections //
    // /////////// //

    // Widgets / controllers connections

    // Time
    //    connect(timeWidget, SIGNAL(timeUpdated(DateTimeRange)), &sqpApp->timeController(),
    //        SLOT(onTimeToUpdate(DateTimeRange)));
    connect(mainToolBar, &ToolBar::timeUpdated, &sqpApp->timeController(),
        &TimeController::setDateTimeRange);

    // Widgets / widgets connections

    // For the following connections, we use DirectConnection to allow each widget that can
    // potentially attach a menu to the variable's menu to do so before this menu is displayed.
    // The order of connections is also important, since it determines the order in which each
    // widget will attach its menu
    connect(m_Ui->variableInspectorWidget,
        SIGNAL(tableMenuAboutToBeDisplayed(QMenu*, const QVector<std::shared_ptr<Variable>>&)),
        m_Ui->view, SLOT(attachVariableMenu(QMenu*, const QVector<std::shared_ptr<Variable>>&)),
        Qt::DirectConnection);
}

MainWindow::~MainWindow() {}

void MainWindow::changeEvent(QEvent* e)
{
    QMainWindow::changeEvent(e);
    switch (e->type())
    {
        case QEvent::LanguageChange:
            m_Ui->retranslateUi(this);
            break;
        default:
            break;
    }
}

void MainWindow::closeEvent(QCloseEvent* event)
{
    if (!impl->checkDataToSave(this))
    {
        event->ignore();
    }
    else
    {
        event->accept();
    }
}

void MainWindow::keyPressEvent(QKeyEvent* event)
{
    switch (event->key())
    {
        case Qt::Key_F11:
            if (this->isFullScreen())
            {
                this->showNormal();
            }
            else
            {
                this->showFullScreen();
            }
            break;
        default:
            break;
    }
}

bool MainWindow::MainWindowPrivate::checkDataToSave(QWidget* parentWidget)
{
    //    auto hasChanges = sqpApp->catalogueController().hasChanges();
    //    if (hasChanges)
    //    {
    //        // There are some unsaved changes
    //        switch (QMessageBox::question(parentWidget, tr("Save changes"),
    //            tr("The catalogue controller has unsaved changes.\nDo you want to save them ?"),
    //            QMessageBox::SaveAll | QMessageBox::Discard | QMessageBox::Cancel,
    //            QMessageBox::SaveAll))
    //        {
    //            case QMessageBox::SaveAll:
    //                sqpApp->catalogueController().saveAll();
    //                break;
    //            case QMessageBox::Discard:
    //                break;
    //            case QMessageBox::Cancel:
    //            default:
    //                return false;
    //        }
    //    }

    return true;
}
