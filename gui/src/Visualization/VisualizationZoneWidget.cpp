#include "Visualization/VisualizationZoneWidget.h"

#include "Data/SqpDateTime.h"

#include "Visualization/IVisualizationWidgetVisitor.h"
#include "Visualization/VisualizationGraphWidget.h"
#include "ui_VisualizationZoneWidget.h"


#include <SqpApplication.h>

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

VisualizationZoneWidget::VisualizationZoneWidget(const QString &name, QWidget *parent)
        : QWidget{parent}, ui{new Ui::VisualizationZoneWidget}
{
    ui->setupUi(this);

    ui->zoneNameLabel->setText(name);

    // 'Close' options : widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
    connect(ui->closeButton, &QToolButton::clicked, this, &VisualizationZoneWidget::close);
    ui->closeButton->setIcon(sqpApp->style()->standardIcon(QStyle::SP_TitleBarCloseButton));
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

    this->addGraph(graphWidget);

    graphWidget->addVariable(variable);

    // Lambda to synchronize zone widget
    auto synchronizeZoneWidget = [this, graphWidget](const SqpDateTime &dateTime,
                                                     const SqpDateTime &oldDateTime,
                                                     VisualizationGraphWidgetZoomType zoomType) {
        auto frameLayout = ui->visualizationZoneFrame->layout();
        for (auto i = 0; i < frameLayout->count(); ++i) {
            auto graphChild
                = dynamic_cast<VisualizationGraphWidget *>(frameLayout->itemAt(i)->widget());
            if (graphChild && (graphChild != graphWidget)) {

                auto dateTimeThatKeepDelta = dateTime;
                auto graphChildRange = graphChild->graphRange();
                switch (zoomType) {
                    case VisualizationGraphWidgetZoomType::ZoomIn: {
                        auto deltaLeft = dateTime.m_TStart - oldDateTime.m_TStart;
                        auto deltaRight = oldDateTime.m_TEnd - dateTime.m_TEnd;
                        graphChildRange.m_TStart += deltaLeft;
                        graphChildRange.m_TEnd -= deltaRight;
                        dateTimeThatKeepDelta = graphChildRange;
                        break;
                    }

                    case VisualizationGraphWidgetZoomType::ZoomOut: {
                        auto deltaLeft = oldDateTime.m_TStart - dateTime.m_TStart;
                        auto deltaRight = dateTime.m_TEnd - oldDateTime.m_TEnd;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd += deltaRight;
                        dateTimeThatKeepDelta = graphChildRange;
                        break;
                    }
                    case VisualizationGraphWidgetZoomType::PanRight: {
                        auto deltaRight = dateTime.m_TEnd - oldDateTime.m_TEnd;
                        graphChildRange.m_TStart += deltaRight;
                        graphChildRange.m_TEnd += deltaRight;
                        dateTimeThatKeepDelta = graphChildRange;
                        break;
                    }
                    case VisualizationGraphWidgetZoomType::PanLeft: {
                        auto deltaLeft = oldDateTime.m_TStart - dateTime.m_TStart;
                        graphChildRange.m_TStart -= deltaLeft;
                        graphChildRange.m_TEnd -= deltaLeft;
                        dateTimeThatKeepDelta = graphChildRange;
                        break;
                    }
                    case VisualizationGraphWidgetZoomType::Unknown: {
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
                graphChild->enableSynchronize(false);
                graphChild->setGraphRange(dateTimeThatKeepDelta);
                graphChild->enableSynchronize(true);
            }
        }
    };

    // connection for synchronization
    connect(graphWidget, &VisualizationGraphWidget::synchronize, synchronizeZoneWidget);

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
