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

#include <DataSource/DataSourceController.h>
#include <DataSource/DataSourceWidget.h>
#include <SqpApplication.h>

#include <QAction>
#include <QDate>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
//#include <omp.h>
//#include <network/filedownloader.h>
//#include <qlopdatabase.h>
//#include <qlopsettings.h>
//#include <qlopgui.h>
//#include <spacedata.h>
//#include "qlopcore.h"
//#include "qlopcodecmanager.h"
//#include "cdfcodec.h"
//#include "amdatxtcodec.h"
//#include <qlopplotmanager.h>
#include <QAction>
#include <QToolBar>
#include <memory.h>
MainWindow::MainWindow(QWidget *parent) : QMainWindow{parent}, m_Ui{new Ui::MainWindow}
{
    m_Ui->setupUi(this);

    auto leftSidePane = m_Ui->leftInspectorSidePane->sidePane();
    leftSidePane->addAction("ACTION L1");
    leftSidePane->addAction("ACTION L2");
    leftSidePane->addAction("ACTION L3");

    auto rightSidePane = m_Ui->rightInspectorSidePane->sidePane();
    rightSidePane->addAction("ACTION R1");
    rightSidePane->addAction("ACTION R2");
    rightSidePane->addAction("ACTION R3");

    this->menuBar()->addAction("File");
    auto mainToolBar = this->addToolBar("MainToolBar");
    mainToolBar->addAction("A1");

    // Widgets / controllers connections
    connect(&sqpApp->dataSourceController(), SIGNAL(dataSourceItemSet(DataSourceItem *)),
            m_Ui->dataSourceWidget, SLOT(addDataSource(DataSourceItem *)));

    /*    QLopGUI::registerMenuBar(menuBar());
        this->setWindowIcon(QIcon(":/sciqlopLOGO.svg"));
        this->m_progressWidget = new QWidget();
        this->m_progressLayout = new QVBoxLayout(this->m_progressWidget);
        this->m_progressWidget->setLayout(this->m_progressLayout);
        this->m_progressWidget->setWindowModality(Qt::WindowModal);
        m_progressThreadIds = (int*) malloc(OMP_THREADS*sizeof(int));
        for(int i=0;i<OMP_THREADS;i++)
        {
            this->m_progress.append(new QProgressBar(this->m_progressWidget));
            this->m_progress.last()->setMinimum(0);
            this->m_progress.last()->setMaximum(100);
            this->m_progressLayout->addWidget(this->m_progress.last());
            this->m_progressWidget->hide();
            this->m_progressThreadIds[i] = -1;
        }
        this->m_progressWidget->setWindowTitle("Loading File");
        const QList<QLopService*>ServicesToLoad=QList<QLopService*>()
                << QLopCore::self()
                << QLopPlotManager::self()
                << QLopCodecManager::self()
                << FileDownloader::self()
                << QLopDataBase::self()
                << SpaceData::self();

        CDFCodec::registerToManager();
        AMDATXTCodec::registerToManager();


        for(int i=0;i<ServicesToLoad.count();i++)
        {
            qDebug()<<ServicesToLoad.at(i)->serviceName();
            ServicesToLoad.at(i)->initialize(); //must be called before getGUI
            QDockWidget* wdgt=ServicesToLoad.at(i)->getGUI();
            if(wdgt)
            {
                wdgt->setAllowedAreas(Qt::AllDockWidgetAreas);
                this->addDockWidget(Qt::TopDockWidgetArea,wdgt);
            }
            PythonQt::self()->getMainModule().addObject(ServicesToLoad.at(i)->serviceName(),(QObject*)ServicesToLoad.at(i));
        }*/
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
