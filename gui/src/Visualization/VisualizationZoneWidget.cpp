#include "Visualization/VisualizationZoneWidget.h"


#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "ui_VisualizationZoneWidget.h"

#include <Data/SqpRange.h>
#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <QUuid>
#include <SqpApplication.h>
#include <cmath>

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

} // namespace

struct VisualizationZoneWidget::VisualizationZoneWidgetPrivate {

    explicit VisualizationZoneWidgetPrivate() : m_SynchronisationGroupId{QUuid::createUuid()} {}
    QUuid m_SynchronisationGroupId;
};

VisualizationZoneWidget::VisualizationZoneWidget(const QString &name, QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationZoneWidget},
          impl{spimpl::make_unique_impl<VisualizationZoneWidgetPrivate>()}
{
    ui->setupUi(this);

    ui->zoneNameLabel->setText(name);

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
    ui->visualizationZoneFrame->layout()->addWidget(graphWidget);
}

VisualizationGraphWidget *VisualizationZoneWidget::createGraph(std::shared_ptr<Variable> variable)
{
    auto graphWidget = new VisualizationGraphWidget{
        defaultGraphName(*ui->visualizationZoneFrame->layout()), this};


    // Set graph properties
    graphWidget->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::MinimumExpanding);
    graphWidget->setMinimumHeight(GRAPH_MINIMUM_HEIGHT);


    // Lambda to synchronize zone widget
    auto synchronizeZoneWidget = [this, graphWidget](const SqpRange &graphRange,
                                                     const SqpRange &oldGraphRange) {

        auto zoomType = VariableController::getZoomType(graphRange, oldGraphRange);
        auto frameLayout = ui->visualizationZoneFrame->layout();
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
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: ZoomIn");
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: deltaLeft")
                                                                  << deltaLeft;
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: deltaRight")
                                                                  << deltaRight;
                        qCCritical(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;

                        break;
                    }

                    case AcquisitionZoomType::ZoomOut: {
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: ZoomOut");
                        auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
                        auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: deltaLeft")
                                                                  << deltaLeft;
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: deltaRight")
                                                                  << deltaRight;
                        qCCritical(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd += deltaRight;
                        break;
                    }
                    case AcquisitionZoomType::PanRight: {
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: PanRight");
                        auto deltaRight = graphRange.m_TEnd - oldGraphRange.m_TEnd;
                        graphChildRange.m_TStart += deltaRight;
                        graphChildRange.m_TEnd += deltaRight;
                        qCCritical(LOG_VisualizationZoneWidget())
                            << tr("TORM: dt") << graphRange.m_TEnd - graphRange.m_TStart;
                        break;
                    }
                    case AcquisitionZoomType::PanLeft: {
                        qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: PanLeft");
                        auto deltaLeft = oldGraphRange.m_TStart - graphRange.m_TStart;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd -= deltaLeft;
                        break;
                    }
                    case AcquisitionZoomType::Unknown: {
                        qCCritical(LOG_VisualizationZoneWidget())
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
                qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: Range before: ")
                                                          << graphChild->graphRange();
                qCCritical(LOG_VisualizationZoneWidget()) << tr("TORM: Range after : ")
                                                          << graphChildRange;
                qCCritical(LOG_VisualizationZoneWidget())
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

    auto range = SqpRange{};

    // Apply visitor to graph children
    auto layout = ui->visualizationZoneFrame->layout();
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

    this->addGraph(graphWidget);

    graphWidget->addVariable(variable, range);

    // get y using variable range
    if (auto dataSeries = variable->dataSeries()) {
        auto valuesBounds = dataSeries->valuesBounds(range.m_TStart, range.m_TEnd);
        auto end = dataSeries->cend();
        if (valuesBounds.first != end && valuesBounds.second != end) {
            auto rangeValue = [](const auto &value) { return std::isnan(value) ? 0. : value; };

            auto minValue = rangeValue(valuesBounds.first->minValue());
            auto maxValue = rangeValue(valuesBounds.second->maxValue());

            graphWidget->setYRange(SqpRange{minValue, maxValue});
        }
    }

    return graphWidget;
}

void VisualizationZoneWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor to graph children
        auto layout = ui->visualizationZoneFrame->layout();
        for (auto i = 0; i < layout->count(); ++i) {
            if (auto item = layout->itemAt(i)) {
                // Widgets different from graphs are not visited (no action)
                if (auto visualizationGraphWidget
                    = dynamic_cast<VisualizationGraphWidget *>(item->widget())) {
                    visualizationGraphWidget->accept(visitor);
                }
            }
        }

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

void VisualizationZoneWidget::onVariableAdded(std::shared_ptr<Variable> variable)
{
    QMetaObject::invokeMethod(&sqpApp->variableController(), "onAddSynchronized",
                              Qt::QueuedConnection, Q_ARG(std::shared_ptr<Variable>, variable),
                              Q_ARG(QUuid, impl->m_SynchronisationGroupId));
}
