#include "visualization/VisualizationWidget.h"
#include "ui_VisualizationWidget.h"
#include "visualization/VisualizationTabWidget.h"

#include <QDebug>
#include <QToolButton>

#include "iostream"

Q_LOGGING_CATEGORY(LOG_VisualizationWidget, "VisualizationWidget")

VisualizationWidget::VisualizationWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::VisualizationWidget}
{
    ui->setupUi(this);

    auto addTabViewButton = new QToolButton{ui->tabWidget};
    addTabViewButton->setText(tr("Add View"));
    addTabViewButton->setCursor(Qt::ArrowCursor);
    addTabViewButton->setAutoRaise(true);
    ui->tabWidget->setCornerWidget(addTabViewButton, Qt::TopRightCorner);

    auto addTabView = [&](bool checked) {
        auto index = ui->tabWidget->addTab(new VisualizationTabWidget(ui->tabWidget),
                                           QString("View %1").arg(ui->tabWidget->count() + 1));
        qCInfo(LOG_VisualizationWidget()) << tr("add the tab of index %1").arg(index);
    };

    auto removeTabView = [&](int index) {
        ui->tabWidget->removeTab(index);
        qCInfo(LOG_VisualizationWidget()) << tr("remove the tab of index %1").arg(index);
    };

    ui->tabWidget->setTabsClosable(true);

    connect(addTabViewButton, &QToolButton::clicked, addTabView);
    connect(ui->tabWidget, &QTabWidget::tabCloseRequested, removeTabView);
}

VisualizationWidget::~VisualizationWidget()
{
    delete ui;
}
