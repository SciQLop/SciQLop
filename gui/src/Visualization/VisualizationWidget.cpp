#include "Visualization/VisualizationWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/qcustomplot.h"

#include "ui_VisualizationWidget.h"

#include <QToolButton>

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
    auto width = ui->tabWidget->cornerWidget()->width();
    auto height = ui->tabWidget->cornerWidget()->height();
    addTabViewButton->setMinimumHeight(height);
    addTabViewButton->setMinimumWidth(width);
    ui->tabWidget->setMinimumHeight(height);
    ui->tabWidget->setMinimumWidth(width);

    auto addTabView = [&]() {
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

void VisualizationWidget::addTab(VisualizationTabWidget *tabWidget)
{
    // NOTE: check is this method has to be deleted because of its dupplicated version visible as
    // lambda function (in the constructor)
}

VisualizationTabWidget *VisualizationWidget::createTab()
{
}

void VisualizationWidget::removeTab(VisualizationTabWidget *tab)
{
    // NOTE: check is this method has to be deleted because of its dupplicated version visible as
    // lambda function (in the constructor)
}

void VisualizationWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
}

void VisualizationWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationWidget::name() const
{
    return QStringLiteral("MainView");
}
