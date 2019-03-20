#include "Visualization/VisualizationWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationActionManager.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationSelectionZoneItem.h"
#include "Visualization/VisualizationSelectionZoneManager.h"
#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/VisualizationZoneWidget.h"
#include "Visualization/operations/FindVariableOperation.h"
#include "Visualization/operations/GenerateVariableMenuOperation.h"
#include "Visualization/operations/RemoveVariableOperation.h"
#include "Visualization/operations/RescaleAxeOperation.h"
#include "Visualization/qcustomplot.h"

#include "ui_VisualizationWidget.h"

#include "DragAndDrop/DragDropGuiController.h"
#include "SqpApplication.h"

#include <QToolButton>

#include <memory>

Q_LOGGING_CATEGORY(LOG_VisualizationWidget, "VisualizationWidget")

struct VisualizationWidget::VisualizationWidgetPrivate
{
    std::unique_ptr<VisualizationSelectionZoneManager> m_ZoneSelectionManager = nullptr;
    VisualizationActionManager m_ActionManager;

    VisualizationWidgetPrivate()
            : m_ZoneSelectionManager(std::make_unique<VisualizationSelectionZoneManager>())
    {
    }
};

VisualizationWidget::VisualizationWidget(QWidget* parent)
        : QWidget { parent }
        , ui { new Ui::VisualizationWidget }
        , impl { spimpl::make_unique_impl<VisualizationWidgetPrivate>() }
{
    ui->setupUi(this);

    auto addTabViewButton = new QToolButton { ui->tabWidget };
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
        auto widget
            = new VisualizationTabWidget { QString { "View %1" }.arg(ui->tabWidget->count() + 1),
                  ui->tabWidget };
        auto index = ui->tabWidget->addTab(widget, widget->name());
        if (ui->tabWidget->count() > 0)
        {
            enableMinimumCornerWidgetSize(false);
        }
        qCInfo(LOG_VisualizationWidget()) << tr("add the tab of index %1").arg(index);
    };

    auto removeTabView = [this, enableMinimumCornerWidgetSize](int index) {
        if (ui->tabWidget->count() == 1)
        {
            enableMinimumCornerWidgetSize(true);
        }

        // Removes widget from tab and closes it
        auto widget = ui->tabWidget->widget(index);
        ui->tabWidget->removeTab(index);
        if (widget)
        {
            widget->close();
        }

        qCInfo(LOG_VisualizationWidget()) << tr("remove the tab of index %1").arg(index);
    };

    ui->tabWidget->setTabsClosable(true);

    connect(addTabViewButton, &QToolButton::clicked, addTabView);
    connect(ui->tabWidget, &QTabWidget::tabCloseRequested, removeTabView);

    sqpApp->dragDropGuiController().addDragDropTabBar(ui->tabWidget->tabBar());

    // Actions
    impl->m_ActionManager.installSelectionZoneActions();

    auto removeZoneAction = new QAction("Remove selected zone(s)");
    removeZoneAction->setShortcut(QKeySequence::Delete);
    connect(removeZoneAction, &QAction::triggered, [this]() {
        auto selection = impl->m_ZoneSelectionManager->selectedItems();
        for (auto selectionZone : selection)
        {
            if (auto graph = selectionZone->parentGraphWidget())
            {
                graph->removeSelectionZone(selectionZone);
            }
        }
    });
    addAction(removeZoneAction);

    // Adds default tab
    addTabView();
}

VisualizationWidget::~VisualizationWidget()
{
    sqpApp->dragDropGuiController().removeDragDropTabBar(ui->tabWidget->tabBar());
    delete ui;
}

VisualizationSelectionZoneManager& VisualizationWidget::selectionZoneManager() const
{
    return *impl->m_ZoneSelectionManager.get();
}

VisualizationTabWidget* VisualizationWidget::currentTabWidget() const
{
    if (auto tab = qobject_cast<VisualizationTabWidget*>(ui->tabWidget->currentWidget()))
    {
        return tab;
    }

    return nullptr;
}

void VisualizationWidget::accept(IVisualizationWidgetVisitor* visitor)
{
    if (visitor)
    {
        visitor->visitEnter(this);

        // Apply visitor for tab children
        for (auto i = 0; i < ui->tabWidget->count(); ++i)
        {
            // Widgets different from tabs are not visited (no action)
            if (auto visualizationTabWidget
                = dynamic_cast<VisualizationTabWidget*>(ui->tabWidget->widget(i)))
            {
                visualizationTabWidget->accept(visitor);
            }
        }

        visitor->visitLeave(this);
    }
    else
    {
        qCCritical(LOG_VisualizationWidget()) << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationWidget::canDrop(Variable2& variable) const
{
    // The main widget can never accomodate a variable
    Q_UNUSED(variable);
    return false;
}

bool VisualizationWidget::contains(Variable2& variable) const
{
    Q_UNUSED(variable);
    return false;
}

QString VisualizationWidget::name() const
{
    return QStringLiteral("MainView");
}

void VisualizationWidget::attachVariableMenu(
    QMenu* menu, const QVector<std::shared_ptr<Variable2>>& variables) noexcept
{
    // Menu is generated only if there is a single variable
    if (variables.size() == 1)
    {
        if (auto variable = variables.first())
        {
            // Gets the containers of the variable
            FindVariableOperation findVariableOperation { variable };
            accept(&findVariableOperation);
            auto variableContainers = findVariableOperation.result();

            // Generates the actions that make it possible to visualize the variable
            GenerateVariableMenuOperation generateVariableMenuOperation { menu, variable,
                std::move(variableContainers) };
            accept(&generateVariableMenuOperation);
        }
        else
        {
            qCCritical(LOG_VisualizationWidget()) << tr(
                "Can't generate the menu relative to the visualization: the variable is null");
        }
    }
    else
    {
        qCDebug(LOG_VisualizationWidget())
            << tr("No generation of the menu related to the visualization: several variables are "
                  "selected");
    }
}

void VisualizationWidget::onVariableAboutToBeDeleted(std::shared_ptr<Variable2> variable) noexcept
{
    // Calls the operation of removing all references to the variable in the visualization
    auto removeVariableOperation = RemoveVariableOperation { variable };
    accept(&removeVariableOperation);
}

void VisualizationWidget::onRangeChanged(
    std::shared_ptr<Variable2> variable, const DateTimeRange& range) noexcept
{
    // Calls the operation of rescaling all graph that contrains variable in the visualization
    auto rescaleVariableOperation = RescaleAxeOperation { variable, range };
    accept(&rescaleVariableOperation);
}

void VisualizationWidget::closeEvent(QCloseEvent* event)
{
    // Closes tabs in the widget
    for (auto i = 0; i < ui->tabWidget->count(); ++i)
    {
        if (auto visualizationTabWidget
            = dynamic_cast<VisualizationTabWidget*>(ui->tabWidget->widget(i)))
        {
            visualizationTabWidget->close();
        }
    }

    QWidget::closeEvent(event);
}
