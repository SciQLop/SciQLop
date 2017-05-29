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
#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QListWidgetItem>
#include <QMainWindow>
#include <QProgressBar>
#include <QProgressDialog>
#include <QThread>
#include <QVBoxLayout>
#include <QWidget>
//#include "../Core/qlopservice.h"
//#include "../Core/qlopgui.h"


namespace Ui {
class MainWindow;
}

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = 0);
    ~MainWindow();
public slots:

protected:
    void changeEvent(QEvent *e);

private:
    Ui::MainWindow *ui;
    QList<QProgressBar *> m_progress;
    int *m_progressThreadIds;
    QWidget *m_progressWidget;
    QVBoxLayout *m_progressLayout;
    // QList<QLopService*> m_qlopServices;
};

#endif // MAINWINDOW_H
