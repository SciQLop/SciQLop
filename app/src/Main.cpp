/*------------------------------------------------------------------------------
-- This file is a part of the QLop Software
-- Copyright (C) 2015, Plasma Physics Laboratory - CNRS
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
#include <QProcessEnvironment>
#include <QThread>
#include <SqpApplication.h>
#include <qglobal.h>

#include <PluginManager/PluginManager.h>
#include <QDir>
#include <QtPlugin>

#include <QLoggingCategory>

Q_LOGGING_CATEGORY(LOG_Main, "Main")

namespace
{

const auto PLUGIN_DIRECTORY_NAME = QStringLiteral("plugins");


} // namespace

int main(int argc, char* argv[])
{
#ifdef QT_STATICPLUGIN
#ifndef SQP_NO_PLUGINS
    Q_IMPORT_PLUGIN(PythonProviders)
    Q_INIT_RESOURCE(python_providers);
#endif
#endif
    Q_INIT_RESOURCE(sqpguiresources);

    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");

    QGuiApplication::setAttribute(Qt::AA_EnableHighDpiScaling);

    SqpApplication a { argc, argv };

    MainWindow w;
    w.show();

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
            qCDebug(LOG_Main())
                << QObject::tr("Plugin directory: %1").arg(directory.absolutePath());
            pluginManager.loadPlugins(directory);
        }
    }
    pluginManager.loadStaticPlugins();

    return a.exec();
}
