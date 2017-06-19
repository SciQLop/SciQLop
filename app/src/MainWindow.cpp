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
#include <SidePane/SqpSidePane.h>
#include <SqpApplication.h>
#include <TimeWidget/TimeWidget.h>
#include <Variable/Variable.h>
#include <Visualization/VisualizationController.h>

#include <QAction>
#include <QDate>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QToolBar>
#include <QToolButton>
#include <memory.h>

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
    QSize m_LastOpenLeftInspectorSize;
    QSize m_LastOpenRightInspectorSize;
};

MainWindow::MainWindow(QWidget *parent)
        : QMainWindow{parent},
          m_Ui{new Ui::MainWindow},
          impl{spimpl::make_unique_impl<MainWindowPrivate>()}
{
    m_Ui->setupUi(this);

    m_Ui->splitter->setCollapsible(LEFTINSPECTORSIDEPANESPLITTERINDEX, false);
    m_Ui->splitter->setCollapsible(RIGHTINSPECTORSIDEPANESPLITTERINDEX, false);


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

        action->setIcon(QIcon{(checked xor right) ? ":/icones/next.png" : ":/icones/previous.png"});

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

    this->menuBar()->addAction(tr("File"));
    auto mainToolBar = this->addToolBar(QStringLiteral("MainToolBar"));

    mainToolBar->addWidget(new TimeWidget{});

    // Widgets / controllers connections
    connect(&sqpApp->dataSourceController(), SIGNAL(dataSourceItemSet(DataSourceItem *)),
            m_Ui->dataSourceWidget, SLOT(addDataSource(DataSourceItem *)));

    qRegisterMetaType<std::shared_ptr<Variable> >();
    connect(&sqpApp->visualizationController(), SIGNAL(variableCreated(std::shared_ptr<Variable>)),
            m_Ui->view, SLOT(displayVariable(std::shared_ptr<Variable>)));

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
