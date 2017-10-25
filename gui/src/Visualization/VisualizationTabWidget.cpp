#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "ui_VisualizationTabWidget.h"

#include "Visualization/VisualizationZoneWidget.h"
#include "Visualization/VisualizationGraphWidget.h"

#include "Variable/VariableController.h"

#include "SqpApplication.h"
#include "DragDropHelper.h"

Q_LOGGING_CATEGORY(LOG_VisualizationTabWidget, "VisualizationTabWidget")

namespace {

/// Generates a default name for a new zone, according to the number of zones already displayed in
/// the tab
QString defaultZoneName(const QLayout &layout)
{
    auto count = 0;
    for (auto i = 0; i < layout.count(); ++i) {
        if (dynamic_cast<VisualizationZoneWidget *>(layout.itemAt(i)->widget())) {
            count++;
        }
    }

    return QObject::tr("Zone %1").arg(count + 1);
}

/**
 * Applies a function to all zones of the tab represented by its layout
 * @param layout the layout that contains zones
 * @param fun the function to apply to each zone
 */
template <typename Fun>
void processZones(QLayout &layout, Fun fun)
{
    for (auto i = 0; i < layout.count(); ++i) {
        if (auto item = layout.itemAt(i)) {
            if (auto visualizationZoneWidget
                = dynamic_cast<VisualizationZoneWidget *>(item->widget())) {
                fun(*visualizationZoneWidget);
            }
        }
    }
}

} // namespace

struct VisualizationTabWidget::VisualizationTabWidgetPrivate {
    explicit VisualizationTabWidgetPrivate(const QString &name) : m_Name{name} {}

    QString m_Name;
};

VisualizationTabWidget::VisualizationTabWidget(const QString &name, QWidget *parent)
        : QWidget{parent},
          ui{new Ui::VisualizationTabWidget},
          impl{spimpl::make_unique_impl<VisualizationTabWidgetPrivate>(name)}
{
    ui->setupUi(this);

    ui->dragDropContainer->setAcceptedMimeTypes({DragDropHelper::MIME_TYPE_GRAPH, DragDropHelper::MIME_TYPE_ZONE});
    connect(ui->dragDropContainer, &VisualizationDragDropContainer::dropOccured, this, &VisualizationTabWidget::dropMimeData);
    sqpApp->dragDropHelper().addDragDropScrollArea(ui->scrollArea);

    // Widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
}

VisualizationTabWidget::~VisualizationTabWidget()
{
    sqpApp->dragDropHelper().removeDragDropScrollArea(ui->scrollArea);
    delete ui;
}

void VisualizationTabWidget::addZone(VisualizationZoneWidget *zoneWidget)
{
    ui->dragDropContainer->addDragWidget(zoneWidget);
}

void VisualizationTabWidget::insertZone(int index, VisualizationZoneWidget *zoneWidget)
{
     ui->dragDropContainer->insertDragWidget(index, zoneWidget);
}

VisualizationZoneWidget *VisualizationTabWidget::createZone(std::shared_ptr<Variable> variable)
{
    return createZone({variable}, -1);
}

VisualizationZoneWidget *VisualizationTabWidget::createZone(const QList<std::shared_ptr<Variable> > &variables, int index)
{
    auto zoneWidget = createEmptyZone(index);

    // Creates a new graph into the zone
    zoneWidget->createGraph(variables, index);

    return zoneWidget;
}

VisualizationZoneWidget *VisualizationTabWidget::createEmptyZone(int index)
{
    auto zoneWidget = new VisualizationZoneWidget{defaultZoneName(*ui->dragDropContainer->layout()), this};
    this->insertZone(index, zoneWidget);

    return zoneWidget;
}

void VisualizationTabWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor to zone children: widgets different from zones are not visited (no action)
        processZones(tabLayout(), [visitor](VisualizationZoneWidget &zoneWidget) {
            zoneWidget.accept(visitor);
        });

        visitor->visitLeave(this);
    }
    else {
        qCCritical(LOG_VisualizationTabWidget()) << tr("Can't visit widget : the visitor is null");
    }
}

bool VisualizationTabWidget::canDrop(const Variable &variable) const
{
    // A tab can always accomodate a variable
    Q_UNUSED(variable);
    return true;
}

bool VisualizationTabWidget::contains(const Variable &variable) const
{
    Q_UNUSED(variable);
    return false;
}

QString VisualizationTabWidget::name() const
{
    return impl->m_Name;
}

void VisualizationTabWidget::closeEvent(QCloseEvent *event)
{
    // Closes zones in the tab
    processZones(tabLayout(), [](VisualizationZoneWidget &zoneWidget) { zoneWidget.close(); });

    QWidget::closeEvent(event);
}

QLayout &VisualizationTabWidget::tabLayout() const noexcept
{
    return *ui->dragDropContainer->layout();
}

void VisualizationTabWidget::dropMimeData(int index, const QMimeData *mimeData)
{
    auto& helper = sqpApp->dragDropHelper();
    if (mimeData->hasFormat(DragDropHelper::MIME_TYPE_GRAPH))
    {
        auto graphWidget = static_cast<VisualizationGraphWidget*>(helper.getCurrentDragWidget());
        auto parentDragDropContainer = qobject_cast<VisualizationDragDropContainer*>(graphWidget->parentWidget());
        Q_ASSERT(parentDragDropContainer);

        auto nbGraph = parentDragDropContainer->countDragWidget();

        const auto& variables = graphWidget->variables();

        if (!variables.isEmpty())
        {
            if (nbGraph == 1)
            {
                //This is the only graph in the previous zone, close the zone
                graphWidget->parentZoneWidget()->close();
            }
            else
            {
                //Close the graph
                graphWidget->close();
            }

            createZone(variables, index);
        }
        else
        {
            //The graph is empty, create an empty zone and move the graph inside

            auto parentZoneWidget = graphWidget->parentZoneWidget();

            parentDragDropContainer->layout()->removeWidget(graphWidget);

            auto zoneWidget = createEmptyZone(index);
            zoneWidget->addGraph(graphWidget);

            //Close the old zone if it was the only graph inside
            if (nbGraph == 1)
                parentZoneWidget->close();
        }
    }
    else if (mimeData->hasFormat(DragDropHelper::MIME_TYPE_ZONE))
    {
        //Simple move of the zone, no variable operation associated
        auto zoneWidget = static_cast<VisualizationZoneWidget*>(helper.getCurrentDragWidget());
        auto parentDragDropContainer = zoneWidget->parentWidget();
        parentDragDropContainer->layout()->removeWidget(zoneWidget);

        ui->dragDropContainer->insertDragWidget(index, zoneWidget);
    }
}
