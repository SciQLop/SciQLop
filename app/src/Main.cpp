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


namespace
{

const auto PLUGIN_DIRECTORY_NAME = QStringLiteral("plugins");


} // namespace

int main(int argc, char* argv[])
{
    init_resources();
    SqpApplication a { argc, argv };
    load_plugins(a);
    MainWindow w;
    w.show();
    return a.exec();
}
