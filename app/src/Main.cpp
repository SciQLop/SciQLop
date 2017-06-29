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

#include <Plugin/PluginManager.h>
#include <QDir>

namespace {

/// Name of the directory containing the plugins

#if _WIN32 || _WIN64
const auto PLUGIN_DIRECTORY_NAME = QStringLiteral("plugins");
#endif

} // namespace

int main(int argc, char *argv[])
{
    SqpApplication a{argc, argv};
    SqpApplication::setOrganizationName("LPP");
    SqpApplication::setOrganizationDomain("lpp.fr");
    SqpApplication::setApplicationName("SciQLop");
    MainWindow w;
    w.show();

    // Loads plugins
    auto pluginDir = QDir{sqpApp->applicationDirPath()};
#if _WIN32 || _WIN64
    pluginDir.mkdir(PLUGIN_DIRECTORY_NAME);
    pluginDir.cd(PLUGIN_DIRECTORY_NAME);
#endif


#if __GNUC__
#if __x86_64__ || __ppc64__
    if (!pluginDir.cd("../lib64/SciQlop")) {
        pluginDir.cd("../lib64/sciqlop");
    }
#else
    __x86_64__ || __ppc64__ if (!pluginDir.cd("../lib/SciQlop")) { pluginDir.cd("../lib/sciqlop"); }
#endif
#endif
    qCDebug(LOG_PluginManager())
        << QObject::tr("Plugin directory: %1").arg(pluginDir.absolutePath());

    PluginManager pluginManager{};
    pluginManager.loadPlugins(pluginDir);

    return a.exec();
}
