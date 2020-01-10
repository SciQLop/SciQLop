#include "Visualization/VisualizationZoneWidget.h"

#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/QCustomPlotSynchronizer.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "Visualization/VisualizationWidget.h"
#include "ui_VisualizationZoneWidget.h"

#include "MimeTypes/MimeTypes.h"
#include "Common/VisualizationDef.h"

#include <Data/DateTimeRange.h>
#include <Data/DateTimeRangeHelper.h>
#include <DataSource/datasources.h>
#include <Time/TimeController.h>
#include <Variable/Variable2.h>
#include <Variable/VariableController2.h>

#include <Visualization/operations/FindVariableOperation.h>

#include <DragAndDrop/DragDropGuiController.h>
#include <QUuid>
#include <SqpApplication.h>
#include <cmath>

#include <QLayout>
#include <QStyle>

Q_LOGGING_CATEGORY(LOG_VisualizationZoneWidget, "VisualizationZoneWidget")

namespace
{

/**
 * Applies a function to all graphs of the zone represented by its layout
 * @param layout the layout that contains graphs
 * @param fun the function to apply to each graph
 */
template <typename Fun>
void processGraphs(QLayout& layout, Fun fun)
{
    for (auto i = 0; i < layout.count(); ++i)
    {
        if (auto item = layout.itemAt(i))
        {
            if (auto visualizationGraphWidget
                = qobject_cast<VisualizationGraphWidget*>(item->widget()))
            {
                fun(*visualizationGraphWidget);
            }
        }
    }
}

/// Generates a default name for a new graph, according to the number of graphs already displayed in
/// the zone
QString defaultGraphName(QLayout& layout)
{
    QSet<QString> existingNames;
    processGraphs(
        layout, [&existingNames](auto& graphWidget) { existingNames.insert(graphWidget.name()); });

    int zoneNum = 1;
    QString name;
    do
    {
        name = QObject::tr("Graph ").append(QString::number(zoneNum));
        ++zoneNum;
    } while (existingNames.contains(name));

    return name;
}

} // namespace

struct VisualizationZoneWidget::VisualizationZoneWidgetPrivate
{

    explicit VisualizationZoneWidgetPrivate()
            : m_SynchronisationGroupId { QUuid::createUuid() }
            , m_Synchronizer { std::make_unique<QCustomPlotSynchronizer>() }
    {
    }
    QUuid m_SynchronisationGroupId;
    std::unique_ptr<IGraphSynchronizer> m_Synchronizer;

    void dropGraph(int index, VisualizationZoneWidget* zoneWidget);
    void dropVariables(const std::vector<std::shared_ptr<Variable2>>& variables, int index,
        VisualizationZoneWidget* zoneWidget);
    void dropProducts(
        const QVariantList& productsData, int index, VisualizationZoneWidget* zoneWidget);
};

VisualizationZoneWidget::VisualizationZoneWidget(const QString& name, QWidget* parent)
        : VisualizationDragWidget { parent }
        , ui { new Ui::VisualizationZoneWidget }
        , impl { spimpl::make_unique_impl<VisualizationZoneWidgetPrivate>() }
{
    ui->setupUi(this);

    ui->zoneNameLabel->setText(name);

    ui->dragDropContainer->setPlaceHolderType(DragDropGuiController::PlaceHolderType::Graph);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_GRAPH, VisualizationDragDropContainer::DropBehavior::Inserted);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_VARIABLE_LIST, VisualizationDragDropContainer::DropBehavior::InsertedAndMerged);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_PRODUCT_LIST, VisualizationDragDropContainer::DropBehavior::InsertedAndMerged);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_TIME_RANGE, VisualizationDragDropContainer::DropBehavior::Merged);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_ZONE, VisualizationDragDropContainer::DropBehavior::Forbidden);
    ui->dragDropContainer->setMimeType(
        MIME::MIME_TYPE_SELECTION_ZONE, VisualizationDragDropContainer::DropBehavior::Forbidden);
    ui->dragDropContainer->setAcceptMimeDataFunction([this](auto mimeData) {
        return sqpApp->dragDropGuiController().checkMimeDataForVisualization(
            mimeData, ui->dragDropContainer);
    });

    auto acceptDragWidgetFun = [](auto dragWidget, auto mimeData) {
        if (!mimeData)
        {
            return false;
        }

        if (mimeData->hasFormat(MIME::MIME_TYPE_VARIABLE_LIST))
        {
            auto variables = sqpApp->variableController().variables(
                Variable2::IDs(mimeData->data(MIME::MIME_TYPE_VARIABLE_LIST)));

            if (variables.size() != 1)
            {
                return false;
            }
            auto variable = variables.front();

            if (auto graphWidget = dynamic_cast<const VisualizationGraphWidget*>(dragWidget))
            {
                return graphWidget->canDrop(*variable);
            }
        }

        return true;
    };
    ui->dragDropContainer->setAcceptDragWidgetFunction(acceptDragWidgetFun);

    connect(ui->dragDropContainer, &VisualizationDragDropContainer::dropOccuredInContainer, this,
        &VisualizationZoneWidget::dropMimeData);
    connect(ui->dragDropContainer, &VisualizationDragDropContainer::dropOccuredOnWidget, this,
        &VisualizationZoneWidget::dropMimeDataOnGraph);

    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
    connect(ui->closeButton, &QToolButton::clicked, this, &VisualizationZoneWidget::close);
    ui->closeButton->setIcon(sqpApp->style()->standardIcon(QStyle::SP_TitleBarCloseButton));

    // Synchronisation id
    //    QMetaObject::invokeMethod(&sqpApp->variableController(), "onAddSynchronizationGroupId",
    //        Qt::QueuedConnection, Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

VisualizationZoneWidget::~VisualizationZoneWidget()
{
    delete ui;
}

void VisualizationZoneWidget::setZoneRange(const DateTimeRange& range)
{
    if (auto graph = firstGraph())
    {
        graph->setGraphRange(range);
    }
    else
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("setZoneRange:Cannot set the range of an empty zone.");
    }
}

void VisualizationZoneWidget::addGraph(VisualizationGraphWidget* graphWidget)
{
    // Synchronize new graph with others in the zone
    //    impl->m_Synchronizer->addGraph(*graphWidget);

    //    ui->dragDropContainer->addDragWidget(graphWidget);
    insertGraph(0, graphWidget);
}

void VisualizationZoneWidget::insertGraph(int index, VisualizationGraphWidget* graphWidget)
{
    DEPRECATE(
        auto layout = ui->dragDropContainer->layout(); for (int i = 0; i < layout->count(); i++) {
            auto graph = qobject_cast<VisualizationGraphWidget*>(layout->itemAt(i)->widget());
            connect(graphWidget, &VisualizationGraphWidget::setrange_sig, graph,
                &VisualizationGraphWidget::setGraphRange);
            connect(graph, &VisualizationGraphWidget::setrange_sig, graphWidget,
                &VisualizationGraphWidget::setGraphRange);
        } if (auto graph = firstGraph()) { graphWidget->setGraphRange(graph->graphRange(), true); })

    // Synchronize new graph with others in the zone
    impl->m_Synchronizer->addGraph(*graphWidget);

    ui->dragDropContainer->insertDragWidget(index, graphWidget);
}

VisualizationGraphWidget* VisualizationZoneWidget::createGraph(std::shared_ptr<Variable2> variable)
{
    return createGraph(variable, -1);
}

VisualizationGraphWidget* VisualizationZoneWidget::createGraph(
    std::shared_ptr<Variable2> variable, int index)
{
    auto graphWidget
        = new VisualizationGraphWidget { defaultGraphName(*ui->dragDropContainer->layout()), this };


    // Set graph properties
    graphWidget->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::MinimumExpanding);
    graphWidget->setMinimumHeight(GRAPH_MINIMUM_HEIGHT);

    // connection for synchronization
    // connect(graphWidget, &VisualizationGraphWidget::synchronize, synchronizeZoneWidget);
    connect(graphWidget, &VisualizationGraphWidget::variableAdded, this,
        &VisualizationZoneWidget::onVariableAdded);
    connect(graphWidget, &VisualizationGraphWidget::variableAboutToBeRemoved, this,
        &VisualizationZoneWidget::onVariableAboutToBeRemoved);

    auto range = DateTimeRange {};
    if (auto firstGraph = this->firstGraph())
    {
        // Case of a new graph in a existant zone
        range = firstGraph->graphRange();
    }
    else
    {
        // Case of a new graph as the first of the zone
        range = variable->range();
    }

    this->insertGraph(index, graphWidget);

    graphWidget->addVariable(variable, range);
    graphWidget->setYRange(variable);

    return graphWidget;
}

VisualizationGraphWidget* VisualizationZoneWidget::createGraph(
    const std::vector<std::shared_ptr<Variable2>> variables, int index)
{
    if (variables.empty())
    {
        return nullptr;
    }

    auto graphWidget = createGraph(variables.front(), index);
    for (auto variableIt = variables.cbegin() + 1; variableIt != variables.cend(); ++variableIt)
    {
        graphWidget->addVariable(*variableIt, graphWidget->graphRange());
    }

    return graphWidget;
}

VisualizationGraphWidget* VisualizationZoneWidget::firstGraph() const
{
    VisualizationGraphWidget* firstGraph = nullptr;
    auto layout = ui->dragDropContainer->layout();
    if (layout->count() > 0)
    {
        if (auto visualizationGraphWidget
            = qobject_cast<VisualizationGraphWidget*>(layout->itemAt(0)->widget()))
        {
            firstGraph = visualizationGraphWidget;
        }
    }

    return firstGraph;
}

void VisualizationZoneWidget::closeAllGraphs()
{
    processGraphs(*ui->dragDropContainer->layout(),
        [](VisualizationGraphWidget& graphWidget) { graphWidget.close(); });
}

void VisualizationZoneWidget::accept(IVisualizationWidgetVisitor* visitor)
{
    if (visitor)
    {
        visitor->visitEnter(this);

        // Apply visitor to graph children: widgets different from graphs are not visited (no
        // action)
        processGraphs(*ui->dragDropContainer->layout(),
            [visitor](VisualizationGraphWidget& graphWidget) { graphWidget.accept(visitor); });

        visitor->visitLeave(this);
    }
    else
    {
        qCCritical(LOG_VisualizationZoneWidget()) << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationZoneWidget::canDrop(Variable2& variable) const
{
    // A tab can always accomodate a variable
    Q_UNUSED(variable);
    return true;
}

bool VisualizationZoneWidget::contains(Variable2& variable) const
{
    Q_UNUSED(variable);
    return false;
}

QString VisualizationZoneWidget::name() const
{
    return ui->zoneNameLabel->text();
}

QMimeData* VisualizationZoneWidget::mimeData(const QPoint& position) const
{
    Q_UNUSED(position);

    auto mimeData = new QMimeData;
    mimeData->setData(MIME::MIME_TYPE_ZONE, QByteArray {});

    if (auto firstGraph = this->firstGraph())
    {
        auto timeRangeData = TimeController::mimeDataForTimeRange(firstGraph->graphRange());
        mimeData->setData(MIME::MIME_TYPE_TIME_RANGE, timeRangeData);
    }

    return mimeData;
}

bool VisualizationZoneWidget::isDragAllowed() const
{
    return true;
}

void VisualizationZoneWidget::notifyMouseMoveInGraph(const QPointF& graphPosition,
    const QPointF& plotPosition, VisualizationGraphWidget* graphWidget)
{
    processGraphs(*ui->dragDropContainer->layout(),
        [&graphPosition, &plotPosition, &graphWidget](VisualizationGraphWidget& processedGraph) {
            switch (sqpApp->plotsCursorMode())
            {
                case SqpApplication::PlotsCursorMode::Vertical:
                    processedGraph.removeHorizontalCursor();
                    processedGraph.addVerticalCursorAtViewportPosition(graphPosition.x());
                    break;
                case SqpApplication::PlotsCursorMode::Temporal:
                    processedGraph.addVerticalCursor(plotPosition.x());
                    processedGraph.removeHorizontalCursor();
                    break;
                case SqpApplication::PlotsCursorMode::Horizontal:
                    processedGraph.removeVerticalCursor();
                    if (&processedGraph == graphWidget)
                    {
                        processedGraph.addHorizontalCursorAtViewportPosition(graphPosition.y());
                    }
                    else
                    {
                        processedGraph.removeHorizontalCursor();
                    }
                    break;
                case SqpApplication::PlotsCursorMode::Cross:
                    if (&processedGraph == graphWidget)
                    {
                        processedGraph.addVerticalCursorAtViewportPosition(graphPosition.x());
                        processedGraph.addHorizontalCursorAtViewportPosition(graphPosition.y());
                    }
                    else
                    {
                        processedGraph.removeHorizontalCursor();
                        processedGraph.removeVerticalCursor();
                    }
                    break;
                case SqpApplication::PlotsCursorMode::NoCursor:
                    processedGraph.removeHorizontalCursor();
                    processedGraph.removeVerticalCursor();
                    break;
            }
        });
}

void VisualizationZoneWidget::notifyMouseLeaveGraph(VisualizationGraphWidget* graphWidget)
{
    processGraphs(*ui->dragDropContainer->layout(), [](VisualizationGraphWidget& processedGraph) {
        processedGraph.removeHorizontalCursor();
        processedGraph.removeVerticalCursor();
    });
}

void VisualizationZoneWidget::closeEvent(QCloseEvent* event)
{
    // Closes graphs in the zone
    processGraphs(*ui->dragDropContainer->layout(),
        [](VisualizationGraphWidget& graphWidget) { graphWidget.close(); });

    // Delete synchronization group from variable controller
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onRemoveSynchronizationGroupId",
        Qt::QueuedConnection, Q_ARG(QUuid, impl->m_SynchronisationGroupId));

    QWidget::closeEvent(event);
}

void VisualizationZoneWidget::onVariableAdded(std::shared_ptr<Variable2> variable)
{
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onAddSynchronized",
        Qt::QueuedConnection, Q_ARG(std::shared_ptr<Variable2>, variable),
        Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

void VisualizationZoneWidget::onVariableAboutToBeRemoved(std::shared_ptr<Variable2> variable)
{
    QMetaObject::invokeMethod(&sqpApp->variableController(), "desynchronize", Qt::QueuedConnection,
        Q_ARG(std::shared_ptr<Variable2>, variable), Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

void VisualizationZoneWidget::dropMimeData(int index, const QMimeData* mimeData)
{
    if (mimeData->hasFormat(MIME::MIME_TYPE_GRAPH))
    {
        impl->dropGraph(index, this);
    }
    else if (mimeData->hasFormat(MIME::MIME_TYPE_VARIABLE_LIST))
    {
        auto variables = sqpApp->variableController().variables(
            Variable2::IDs(mimeData->data(MIME::MIME_TYPE_VARIABLE_LIST)));
        impl->dropVariables(variables, index, this);
    }
    else if (mimeData->hasFormat(MIME::MIME_TYPE_PRODUCT_LIST))
    {
        auto products = MIME::decode(
            mimeData->data(MIME::MIME_TYPE_PRODUCT_LIST));
        impl->dropProducts(products, index, this);
    }
    else
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationZoneWidget::dropMimeData, unknown MIME data received.");
    }
}

void VisualizationZoneWidget::dropMimeDataOnGraph(
    VisualizationDragWidget* dragWidget, const QMimeData* mimeData)
{
    auto graphWidget = qobject_cast<VisualizationGraphWidget*>(dragWidget);
    if (!graphWidget)
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationZoneWidget::dropMimeDataOnGraph, dropping in an unknown widget, "
                  "drop aborted");
        Q_ASSERT(false);
        return;
    }

    if (mimeData->hasFormat(MIME::MIME_TYPE_VARIABLE_LIST))
    {
        auto variables = sqpApp->variableController().variables(
            Variable2::IDs(mimeData->data(MIME::MIME_TYPE_VARIABLE_LIST)));
        for (const auto& var : variables)
        {
            graphWidget->addVariable(var, graphWidget->graphRange());
        }
    }
    else if (mimeData->hasFormat(MIME::MIME_TYPE_PRODUCT_LIST))
    {
        auto products = MIME::decode(
            mimeData->data(MIME::MIME_TYPE_PRODUCT_LIST));

        auto context = new QObject { this };
        auto range = TimeController::timeRangeForMimeData(mimeData->data(MIME::MIME_TYPE_TIME_RANGE));
        // BTW this is really dangerous, this assumes the next created variable will be this one...
        connect(&sqpApp->variableController(), &VariableController2::variableAdded, context,
            [this, graphWidget, context, range](auto variable) {
                if (sqpApp->variableController().isReady(variable))
                {
                    graphWidget->addVariable(variable, range);
                    delete context;
                }
                else
                {
                    // -> this is pure insanity! this is a workaround to make a bad design work
                    QObject::connect(variable.get(), &Variable2::updated, context,
                        [graphWidget, context, range, variable]() {
                            graphWidget->addVariable(variable, range);
                            delete context;
                        });
                }
            },
            Qt::QueuedConnection);

        auto productPath = products.first().toString();
        QMetaObject::invokeMethod(&sqpApp->dataSources(), "createVariable",
                                  Qt::QueuedConnection, Q_ARG(QString, productPath));
    }
    else if (mimeData->hasFormat(MIME::MIME_TYPE_TIME_RANGE))
    {
        auto range = TimeController::timeRangeForMimeData(mimeData->data(MIME::MIME_TYPE_TIME_RANGE));
        graphWidget->setGraphRange(range, true, true);
    }
    else
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationZoneWidget::dropMimeDataOnGraph, unknown MIME data received.");
    }
}

void VisualizationZoneWidget::VisualizationZoneWidgetPrivate::dropGraph(
    int index, VisualizationZoneWidget* zoneWidget)
{
    auto& helper = sqpApp->dragDropGuiController();

    auto graphWidget = qobject_cast<VisualizationGraphWidget*>(helper.getCurrentDragWidget());
    if (!graphWidget)
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationZoneWidget::dropGraph, drop aborted, the dropped graph is not "
                  "found or invalid.");
        Q_ASSERT(false);
        return;
    }

    auto parentDragDropContainer
        = qobject_cast<VisualizationDragDropContainer*>(graphWidget->parentWidget());
    if (!parentDragDropContainer)
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationZoneWidget::dropGraph, drop aborted, the parent container of "
                  "the dropped graph is not found.");
        Q_ASSERT(false);
        return;
    }

    const auto& variables = graphWidget->variables();

    if (parentDragDropContainer != zoneWidget->ui->dragDropContainer && !variables.empty())
    {
        // The drop didn't occur in the same zone

        // Abort the requests for the variables (if any)
        // Commented, because it's not sure if it's needed or not
        // for (const auto& var : variables)
        //{
        //    sqpApp->variableController().onAbortProgressRequested(var);
        //}

        auto previousParentZoneWidget = graphWidget->parentZoneWidget();
        auto nbGraph = parentDragDropContainer->countDragWidget();
        if (nbGraph == 1)
        {
            // This is the only graph in the previous zone, close the zone
            helper.delayedCloseWidget(previousParentZoneWidget);
        }
        else
        {
            // Close the graph
            helper.delayedCloseWidget(graphWidget);
        }

        // Creates the new graph in the zone
        auto newGraphWidget = zoneWidget->createGraph(variables, index);
        newGraphWidget->addSelectionZones(graphWidget->selectionZoneRanges());
    }
    else
    {
        // The drop occurred in the same zone or the graph is empty
        // Simple move of the graph, no variable operation associated
        parentDragDropContainer->layout()->removeWidget(graphWidget);

        if (variables.empty() && parentDragDropContainer != zoneWidget->ui->dragDropContainer)
        {
            // The graph is empty and dropped in a different zone.
            // Take the range of the first graph in the zone (if existing).
            auto layout = zoneWidget->ui->dragDropContainer->layout();
            if (layout->count() > 0)
            {
                if (auto visualizationGraphWidget
                    = qobject_cast<VisualizationGraphWidget*>(layout->itemAt(0)->widget()))
                {
                    graphWidget->setGraphRange(visualizationGraphWidget->graphRange());
                }
            }
        }

        zoneWidget->ui->dragDropContainer->insertDragWidget(index, graphWidget);
    }
}

void VisualizationZoneWidget::VisualizationZoneWidgetPrivate::dropVariables(
    const std::vector<std::shared_ptr<Variable2>>& variables, int index,
    VisualizationZoneWidget* zoneWidget)
{
    // Note: the AcceptMimeDataFunction (set on the drop container) ensure there is a single and
    // compatible variable here
    if (variables.size() > 1)
    {
        return;
    }
    zoneWidget->createGraph(variables, index);
}

void VisualizationZoneWidget::VisualizationZoneWidgetPrivate::dropProducts(
    const QVariantList& productsData, int index, VisualizationZoneWidget* zoneWidget)
{
    // Note: the AcceptMimeDataFunction (set on the drop container) ensure there is a single and
    // compatible variable here
    if (productsData.count() != 1)
    {
        qCWarning(LOG_VisualizationZoneWidget())
            << tr("VisualizationTabWidget::dropProducts, dropping multiple products, operation "
                  "aborted.");
        return;
    }

    auto context = new QObject { zoneWidget };
    connect(&sqpApp->variableController(), &VariableController2::variableAdded, context,
        [this, index, zoneWidget, context](auto variable) {
            zoneWidget->createGraph(variable, index);
            delete context; // removes the connection
        },
        Qt::QueuedConnection);

    auto productPath = productsData.first().toString();
    QMetaObject::invokeMethod(&sqpApp->dataSources(), "createVariable",
                              Qt::QueuedConnection, Q_ARG(QString, productPath));
}
