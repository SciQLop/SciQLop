#include "Visualization/VisualizationWidget.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"
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
    ui->tabWidget->setCornerWidget(addTabViewButton, Qt::TopRightCorner);

    auto enableMinimunCornerWidgetSize = [this](bool enable) {

        auto tabViewCornerWidget = ui->tabWidget->cornerWidget();
        auto width = enable ? tabViewCornerWidget->width() : 0;
        auto height = enable ? tabViewCornerWidget->height() : 0;
        tabViewCornerWidget->setMinimumHeight(height);
        tabViewCornerWidget->setMinimumWidth(width);
        ui->tabWidget->setMinimumHeight(height);
        ui->tabWidget->setMinimumWidth(width);
    };

    auto addTabView = [this, enableMinimunCornerWidgetSize]() {
        auto index = ui->tabWidget->addTab(new VisualizationTabWidget(ui->tabWidget),
                                           QString("View %1").arg(ui->tabWidget->count() + 1));
        if (ui->tabWidget->count() > 0) {
            enableMinimunCornerWidgetSize(false);
        }
        qCInfo(LOG_VisualizationWidget()) << tr("add the tab of index %1").arg(index);
    };

    auto removeTabView = [this, enableMinimunCornerWidgetSize](int index) {
        if (ui->tabWidget->count() == 1) {
            enableMinimunCornerWidgetSize(true);
        }

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

void VisualizationWidget::displayVariable(std::shared_ptr<Variable> variable) noexcept
{
    if (auto currentTab = dynamic_cast<VisualizationTabWidget *>(ui->tabWidget->currentWidget())) {
        if (auto newZone = currentTab->createZone()) {
            if (auto newGraph = newZone->createGraph()) {
                newGraph->addVariable(variable);
            }
            else {
                qCDebug(LOG_VisualizationWidget())
                    << tr("Can't display the variable : can't create the graph");
            }
        }
        else {
            qCDebug(LOG_VisualizationWidget())
                << tr("Can't display the variable : can't create a new zone in the current tab");
        }
    }
    else {
        qCDebug(LOG_VisualizationWidget())
            << tr("Can't display the variable : there is no current tab");
    }
}
