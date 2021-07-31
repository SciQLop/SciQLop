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
#ifndef SCIQLOP_MAINWINDOW_H
#define SCIQLOP_MAINWINDOW_H

#include <PluginManager/PluginManager.h>
#include <QDir>
#include <QLoggingCategory>
#include <QMainWindow>
#include <QProgressBar>
#include <QProgressDialog>
#include <QThread>
#include <QVBoxLayout>
#include <QWidget>
#include <QtPlugin>
#include <SqpApplication.h>

#include <Common/spimpl.h>

#include <memory>

namespace Ui
{
class MainWindow;
} // namespace Ui


class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    virtual ~MainWindow() override;
public slots:

protected:
    void changeEvent(QEvent* e) override;
    void closeEvent(QCloseEvent* event) override;

    void keyPressEvent(QKeyEvent* event) override;

private:
    std::unique_ptr<Ui::MainWindow> m_Ui;
    //    QWidget *m_progressWidget;
    //    QVBoxLayout *m_progressLayout;
    // QList<QLopService*> m_qlopServices;
    class MainWindowPrivate;
    spimpl::unique_impl_ptr<MainWindowPrivate> impl;
};

inline void init_resources()
{
    Q_IMPORT_PLUGIN(DemoPlugin);
    Q_INIT_RESOURCE(sqpguiresources);
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");

    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);
}

inline void load_plugins(const SqpApplication& a)
{
    // Loads plugins
    auto pluginDir = QDir { a.applicationDirPath() };
    auto pluginLookupPath = {
#if _WIN32 || _WIN64
        a.applicationDirPath() + "/SciQLop"
#else
        a.applicationDirPath() + "/../lib64/SciQLop",
        a.applicationDirPath() + "/../lib64/sciqlop",
        a.applicationDirPath() + "/../lib/SciQLop",
        a.applicationDirPath() + "/../lib/sciqlop",
#endif
    };

#if _WIN32 || _WIN64
    pluginDir.mkdir(PLUGIN_DIRECTORY_NAME);
    pluginDir.cd(PLUGIN_DIRECTORY_NAME);
#endif

    PluginManager pluginManager {};

    for (auto&& path : pluginLookupPath)
    {
        QDir directory { path };
        if (directory.exists())
        {
            pluginManager.loadPlugins(directory);
        }
    }
    pluginManager.loadStaticPlugins();
}

#endif // SCIQLOP_MAINWINDOW_H
