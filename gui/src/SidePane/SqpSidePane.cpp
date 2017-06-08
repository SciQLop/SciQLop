#include "SidePane/SqpSidePane.h"
#include "ui_SqpSidePane.h"

#include <QAction>
#include <QLayout>
#include <QToolBar>

namespace {
static const QString SQPSIDEPANESTYLESHEET
    = "QToolBar {"
      " background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,"
      "                              stop: 0.0 #5a5a5a,"
      "                              stop: 1.0 #414141);"
      " border: none;"
      " border-left: 1px solid #424242;"
      "border-right: 1px solid #393939;"
      " }"

      " QToolButton {"
      "background: none;"
      "border: none;"
      " }";
}

SqpSidePane::SqpSidePane(QWidget *parent) : QWidget{parent}, ui{new Ui::SqpSidePane}
{
    QVBoxLayout *sidePaneLayout = new QVBoxLayout(this);
    sidePaneLayout->setContentsMargins(0, 0, 0, 0);
    this->setLayout(sidePaneLayout);

    ui->setupUi(this);
    m_SidePaneToolbar = new QToolBar(this);
    m_SidePaneToolbar->setOrientation(Qt::Vertical);
    sidePaneLayout->addWidget(m_SidePaneToolbar);

    m_SidePaneToolbar->setStyleSheet(SQPSIDEPANESTYLESHEET);
}

SqpSidePane::~SqpSidePane()
{
    delete ui;
}

QToolBar *SqpSidePane::sidePane()
{
    return m_SidePaneToolbar;
}
