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

#include <QListWidgetItem>
#include <QLoggingCategory>
#include <QMainWindow>
#include <QProgressBar>
#include <QProgressDialog>
#include <QThread>
#include <QVBoxLayout>
#include <QWidget>

#include <Common/spimpl.h>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_MainWindow)

namespace Ui {
class MainWindow;
} // namespace Ui


class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = 0);
    virtual ~MainWindow();
public slots:

protected:
    void changeEvent(QEvent *e);
    void closeEvent(QCloseEvent *event);

private:
    std::unique_ptr<Ui::MainWindow> m_Ui;
    //    QWidget *m_progressWidget;
    //    QVBoxLayout *m_progressLayout;
    // QList<QLopService*> m_qlopServices;
    class MainWindowPrivate;
    spimpl::unique_impl_ptr<MainWindowPrivate> impl;
};

#endif // SCIQLOP_MAINWINDOW_H
