#include "Visualization/VisualizationZoneWidget.h"

#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/QCustomPlotSynchronizer.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "ui_VisualizationZoneWidget.h"

#include <Data/SqpRange.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <DragDropHelper.h>
#include <QUuid>
#include <SqpApplication.h>
#include <cmath>

#include <QLayout>

Q_LOGGING_CATEGORY(LOG_VisualizationZoneWidget, "VisualizationZoneWidget")

namespace {

/// Minimum height for graph added in zones (in pixels)
const auto GRAPH_MINIMUM_HEIGHT = 300;

/// Generates a default name for a new graph, according to the number of graphs already displayed in
/// the zone
QString defaultGraphName(const QLayout &layout)
{
    auto count = 0;
    for (auto i = 0; i < layout.count(); ++i) {
        if (dynamic_cast<VisualizationGraphWidget *>(layout.itemAt(i)->widget())) {
            count++;
        }
    }

    return QObject::tr("Graph %1").arg(count + 1);
}

/**
 * Applies a function to all graphs of the zone represented by its layout
 * @param layout the layout that contains graphs
 * @param fun the function to apply to each graph
 */
template <typename Fun>
void processGraphs(QLayout &layout, Fun fun)
{
    for (auto i = 0; i < layout.count(); ++i) {
        if (auto item = layout.itemAt(i)) {
            if (auto visualizationGraphWidget
                = dynamic_cast<VisualizationGraphWidget *>(item->widget())) {
                fun(*visualizationGraphWidget);
            }
        }
    }
}

} // namespace

struct VisualizationZoneWidget::VisualizationZoneWidgetPrivate {

    explicit VisualizationZoneWidgetPrivate()
            : m_SynchronisationGroupId{QUuid::createUuid()},
              m_Synchronizer{std::make_unique<QCustomPlotSynchronizer>()}
    {
    }
    QUuid m_SynchronisationGroupId;
    std::unique_ptr<IGraphSynchronizer> m_Synchronizer;
};

VisualizationZoneWidget::VisualizationZoneWidget(const QString &name, QWidget *parent)
        : VisualizationDragWidget{parent},
          ui{new Ui::VisualizationZoneWidget},
          impl{spimpl::make_unique_impl<VisualizationZoneWidgetPrivate>()}
{
    ui->setupUi(this);

    ui->zoneNameLabel->setText(name);

    ui->dragDropContainer->setAcceptedMimeTypes({DragDropHelper::MIME_TYPE_GRAPH});
    connect(ui->dragDropContainer, &VisualizationDragDropContainer::dropOccured, this,
            &VisualizationZoneWidget::dropMimeData);

    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
    connect(ui->closeButton, &QToolButton::clicked, this, &VisualizationZoneWidget::close);
    ui->closeButton->setIcon(sqpApp->style()->standardIcon(QStyle::SP_TitleBarCloseButton));

    // Synchronisation id
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onAddSynchronizationGroupId",
                              Qt::QueuedConnection, Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

VisualizationZoneWidget::~VisualizationZoneWidget()
{
    delete ui;
}

void VisualizationZoneWidget::addGraph(VisualizationGraphWidget *graphWidget)
{
    // Synchronize new graph with others in the zone
    impl->m_Synchronizer->addGraph(*graphWidget);

    ui->dragDropContainer->addDragWidget(graphWidget);
}

void VisualizationZoneWidget::insertGraph(int index, VisualizationGraphWidget *graphWidget)
{
    // Synchronize new graph with others in the zone
    impl->m_Synchronizer->addGraph(*graphWidget);

    ui->dragDropContainer->insertDragWidget(index, graphWidget);
}

VisualizationGraphWidget *VisualizationZoneWidget::createGraph(std::shared_ptr<Variable> variable)
{
    return createGraph(variable, -1);
}

VisualizationGraphWidget *VisualizationZoneWidget::createGraph(std::shared_ptr<Variable> variable,
                                                               int index)
{
    auto graphWidget
        = new VisualizationGraphWidget{defaultGraphName(*ui->dragDropContainer->layout()), this};


    // Set graph properties
    graphWidget->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::MinimumExpanding);
    graphWidget->setMinimumHeight(GRAPH_MINIMUM_HEIGHT);


    // Lambda to synchronize zone widget
    auto synchronizeZoneWidget = [this, graphWidget](const SqpRange &graphRange,
                                                     const SqpRange &oldGraphRange) {

        auto zoomType = VariableController::getZoomType(graphRange, oldGraphRange);
        auto frameLayout = ui->dragDropContainer->layout();
        for (auto i = 0; i < frameLayout->count(); ++i) {
            auto graphChild
                = dynamic_cast<VisualizationGraphWidget *>(frameLayout->itemAt(i)->widget());
            if (graphChild && (graphChild != graphWidget)) {

                auto graphChildRange = graphChild->graphRange();
                switch (zoomType) {
                    case AcquisitionZoomType::ZoomIn: {
                        auto deltaLeft = graphRange.m_TStart - oldGraphRange.m_TStart;
                        auto deltaRight = oldGraphRange.m_TEnd - graphRange.m_TEnd;
                        graphChildRange.m_TStart += deltaLeft;
                        graphChildRange.m_TEnd -= deltaRight;
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: ZoomIn");
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: deltaLeft")
                                                               << deltaLeft;
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: deltaRight")
                                                               << deltaRight;
                        qCDebug(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;

                        break;
                    }

                    case AcquisitionZoomType::ZoomOut: {
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: ZoomOut");
                        auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
                        auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: deltaLeft")
                                                               << deltaLeft;
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: deltaRight")
                                                               << deltaRight;
                        qCDebug(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd += deltaRight;
                        break;
                    }
                    case AcquisitionZoomType::PanRight: {
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: PanRight");
                        auto deltaLeft = graphRange.m_TStart - oldGraphRange.m_TStart;
                        auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
                        graphChildRange.m_TStart += deltaLeft;
                        graphChildRange.m_TEnd += deltaRight;
                        qCDebug(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;
                        break;
                    }
                    case AcquisitionZoomType::PanLeft: {
                        qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: PanLeft");
                        auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
                        auto deltaRight = oldGraphRange.m_TEnd - graphRange.m_TEnd;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd -= deltaRight;
                        break;
                    }
                    case AcquisitionZoomType::Unknown: {
                        qCDebug(LOG_VisualizationZoneWidget())
                            << tr("Impossible to synchronize: zoom type unknown");
                        break;
                    }
                    default:
                        qCCritical(LOG_VisualizationZoneWidget())
                            << tr("Impossible to synchronize: zoom type not take into account");
                        // No action
                        break;
                }
                graphChild->enableAcquisition(false);
                qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: Range before: ")
                                                       << graphChild->graphRange();
                qCDebug(LOG_VisualizationZoneWidget()) << tr("TORM: Range after : ")
                                                       << graphChildRange;
                qCDebug(LOG_VisualizationZoneWidget())
                    << tr("TORM: child dt") << graphChildRange.m_TEnd - graphChildRange.m_TStart;
                graphChild->setGraphRange(graphChildRange);
                graphChild->enableAcquisition(true);
            }
        }
    };

    // connection for synchronization
    connect(graphWidget, &VisualizationGraphWidget::synchronize, synchronizeZoneWidget);
    connect(graphWidget, &VisualizationGraphWidget::variableAdded, this,
            &VisualizationZoneWidget::onVariableAdded);
    connect(graphWidget, &VisualizationGraphWidget::variableAboutToBeRemoved, this,
            &VisualizationZoneWidget::onVariableAboutToBeRemoved);

    auto range = SqpRange{};

    // Apply visitor to graph children
    auto layout = ui->dragDropContainer->layout();
    if (layout->count() > 0) {
        // Case of a new graph in a existant zone
        if (auto visualizationGraphWidget
            = dynamic_cast<VisualizationGraphWidget *>(layout->itemAt(0)->widget())) {
            range = visualizationGraphWidget->graphRange();
        }
    }
    else {
        // Case of a new graph as the first of the zone
        range = variable->range();
    }

    this->insertGraph(index, graphWidget);

    graphWidget->addVariable(variable, range);

    // get y using variable range
    if (auto dataSeries = variable->dataSeries()) {
        dataSeries->lockRead();
        auto valuesBounds
            = dataSeries->valuesBounds(variable->range().m_TStart, variable->range().m_TEnd);
        auto end = dataSeries->cend();
        if (valuesBounds.first != end && valuesBounds.second != end) {
            auto rangeValue = [](const auto &value) { return std::isnan(value) ? 0. : value; };

            auto minValue = rangeValue(valuesBounds.first->minValue());
            auto maxValue = rangeValue(valuesBounds.second->maxValue());

            graphWidget->setYRange(SqpRange{minValue, maxValue});
        }
        dataSeries->unlock();
    }

    return graphWidget;
}

VisualizationGraphWidget *
VisualizationZoneWidget::createGraph(const QList<std::shared_ptr<Variable> > variables, int index)
{
    if (variables.isEmpty()) {
        return nullptr;
    }

    auto graphWidget = createGraph(variables.first(), index);
    for (auto variableIt = variables.cbegin() + 1; variableIt != variables.cend(); ++variableIt) {
        graphWidget->addVariable(*variableIt, graphWidget->graphRange());
    }

    return graphWidget;
}

void VisualizationZoneWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor to graph children: widgets different from graphs are not visited (no
        // action)
        processGraphs(
            *ui->dragDropContainer->layout(),
            [visitor](VisualizationGraphWidget &graphWidget) { graphWidget.accept(visitor); });

        visitor->visitLeave(this);
    }
    else {
        qCCritical(LOG_VisualizationZoneWidget()) << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationZoneWidget::canDrop(const Variable &variable) const
{
    // A tab can always accomodate a variable
    Q_UNUSED(variable);
    return true;
}

bool VisualizationZoneWidget::contains(const Variable &variable) const
{
    Q_UNUSED(variable);
    return false;
}

QString VisualizationZoneWidget::name() const
{
    return ui->zoneNameLabel->text();
}

QMimeData *VisualizationZoneWidget::mimeData() const
{
    auto *mimeData = new QMimeData;
    mimeData->setData(DragDropHelper::MIME_TYPE_ZONE, QByteArray());

    return mimeData;
}

bool VisualizationZoneWidget::isDragAllowed() const
{
    return true;
}

void VisualizationZoneWidget::closeEvent(QCloseEvent *event)
{
    // Closes graphs in the zone
    processGraphs(*ui->dragDropContainer->layout(),
                  [](VisualizationGraphWidget &graphWidget) { graphWidget.close(); });

    // Delete synchronization group from variable controller
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onRemoveSynchronizationGroupId",
                              Qt::QueuedConnection, Q_ARG(QUuid, impl->m_SynchronisationGroupId));

    QWidget::closeEvent(event);
}

void VisualizationZoneWidget::onVariableAdded(std::shared_ptr<Variable> variable)
{
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onAddSynchronized",
                              Qt::QueuedConnection, Q_ARG(std::shared_ptr<Variable>, variable),
                              Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

void VisualizationZoneWidget::onVariableAboutToBeRemoved(std::shared_ptr<Variable> variable)
{
    QMetaObject::invokeMethod(&sqpApp->variableController(), "desynchronize", Qt::QueuedConnection,
                              Q_ARG(std::shared_ptr<Variable>, variable),
                              Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}

void VisualizationZoneWidget::dropMimeData(int index, const QMimeData *mimeData)
{
    auto &helper = sqpApp->dragDropHelper();
    if (mimeData->hasFormat(DragDropHelper::MIME_TYPE_GRAPH)) {
        auto graphWidget = static_cast<VisualizationGraphWidget *>(helper.getCurrentDragWidget());
        auto parentDragDropContainer
            = qobject_cast<VisualizationDragDropContainer *>(graphWidget->parentWidget());
        Q_ASSERT(parentDragDropContainer);

        const auto &variables = graphWidget->variables();

        if (parentDragDropContainer != ui->dragDropContainer && !variables.isEmpty()) {
            // The drop didn't occur in the same zone

            // Abort the requests for the variables (if any)
            // Commented, because it's not sure if it's needed or not
            // for (const auto& var : variables)
            //{
            //    sqpApp->variableController().onAbortProgressRequested(var);
            //}

            auto previousParentZoneWidget = graphWidget->parentZoneWidget();
            auto nbGraph = parentDragDropContainer->countDragWidget();
            if (nbGraph == 1) {
                // This is the only graph in the previous zone, close the zone
                previousParentZoneWidget->close();
            }
            else {
                // Close the graph
                graphWidget->close();
            }

            // Creates the new graph in the zone
            createGraph(variables, index);
        }
        else {
            // The drop occurred in the same zone or the graph is empty
            // Simple move of the graph, no variable operation associated
            parentDragDropContainer->layout()->removeWidget(graphWidget);

            if (variables.isEmpty() && parentDragDropContainer != ui->dragDropContainer) {
                // The graph is empty and dropped in a different zone.
                // Take the range of the first graph in the zone (if existing).
                auto layout = ui->dragDropContainer->layout();
                if (layout->count() > 0) {
                    if (auto visualizationGraphWidget
                        = qobject_cast<VisualizationGraphWidget *>(layout->itemAt(0)->widget())) {
                        graphWidget->setGraphRange(visualizationGraphWidget->graphRange());
                    }
                }
            }

            ui->dragDropContainer->insertDragWidget(index, graphWidget);
        }
    }
}
