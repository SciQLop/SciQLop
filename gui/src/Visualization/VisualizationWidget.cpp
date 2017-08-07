#include "Visualization/VisualizationWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"
#include "Visualization/operations/GenerateVariableMenuOperation.h"
#include "Visualization/operations/RemoveVariableOperation.h"
#include "Visualization/operations/RescaleAxeOperation.h"
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

    auto enableMinimumCornerWidgetSize = [this](bool enable) {

        auto tabViewCornerWidget = ui->tabWidget->cornerWidget();
        auto width = enable ? tabViewCornerWidget->width() : 0;
        auto height = enable ? tabViewCornerWidget->height() : 0;
        tabViewCornerWidget->setMinimumHeight(height);
        tabViewCornerWidget->setMinimumWidth(width);
        ui->tabWidget->setMinimumHeight(height);
        ui->tabWidget->setMinimumWidth(width);
    };

    auto addTabView = [this, enableMinimumCornerWidgetSize]() {
        auto widget = new VisualizationTabWidget{QString{"View %1"}.arg(ui->tabWidget->count() + 1),
                                                 ui->tabWidget};
        auto index = ui->tabWidget->addTab(widget, widget->name());
        if (ui->tabWidget->count() > 0) {
            enableMinimumCornerWidgetSize(false);
        }
        qCInfo(LOG_VisualizationWidget()) << tr("add the tab of index %1").arg(index);
    };

    auto removeTabView = [this, enableMinimumCornerWidgetSize](int index) {
        if (ui->tabWidget->count() == 1) {
            enableMinimumCornerWidgetSize(true);
        }

        // Removes widget from tab and closes it
        auto widget = ui->tabWidget->widget(index);
        ui->tabWidget->removeTab(index);
        if (widget) {
            widget->close();
        }

        qCInfo(LOG_VisualizationWidget()) << tr("remove the tab of index %1").arg(index);

    };

    ui->tabWidget->setTabsClosable(true);

    connect(addTabViewButton, &QToolButton::clicked, addTabView);
    connect(ui->tabWidget, &QTabWidget::tabCloseRequested, removeTabView);

    // Adds default tab
    addTabView();
}

VisualizationWidget::~VisualizationWidget()
{
    delete ui;
}

void VisualizationWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor for tab children
        for (auto i = 0; i < ui->tabWidget->count(); ++i) {
            // Widgets different from tabs are not visited (no action)
            if (auto visualizationTabWidget
                = dynamic_cast<VisualizationTabWidget *>(ui->tabWidget->widget(i))) {
                visualizationTabWidget->accept(visitor);
            }
        }

        visitor->visitLeave(this);
    }
    else {
        qCCritical(LOG_VisualizationWidget()) << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationWidget::canDrop(const Variable &variable) const
{
    // The main widget can never accomodate a variable
    Q_UNUSED(variable);
    return false;
}

bool VisualizationWidget::contains(const Variable &variable) const
{
    Q_UNUSED(variable);
    return false;
}

QString VisualizationWidget::name() const
{
    return QStringLiteral("MainView");
}

void VisualizationWidget::attachVariableMenu(
    QMenu *menu, const QVector<std::shared_ptr<Variable> > &variables) noexcept
{
    // Menu is generated only if there is a single variable
    if (variables.size() == 1) {
        if (auto variable = variables.first()) {
            // Generates the actions that make it possible to visualize the variable
            auto generateVariableMenuOperation = GenerateVariableMenuOperation{menu, variable};
            accept(&generateVariableMenuOperation);
        }
        else {
            qCCritical(LOG_VisualizationWidget()) << tr(
                "Can't generate the menu relative to the visualization: the variable is null");
        }
    }
    else {
        qCDebug(LOG_VisualizationWidget())
            << tr("No generation of the menu related to the visualization: several variables are "
                  "selected");
    }
}

void VisualizationWidget::onVariableAboutToBeDeleted(std::shared_ptr<Variable> variable) noexcept
{
    // Calls the operation of removing all references to the variable in the visualization
    auto removeVariableOperation = RemoveVariableOperation{variable};
    accept(&removeVariableOperation);
}

void VisualizationWidget::onRangeChanged(std::shared_ptr<Variable> variable,
                                         const SqpRange &range) noexcept
{
    // Calls the operation of rescaling all graph that contrains variable in the visualization
    auto rescaleVariableOperation = RescaleAxeOperation{variable, range};
    accept(&rescaleVariableOperation);
}
