#include "Visualization/VisualizationTabWidget.h"
#include "Visualization/IVisualizationWidgetVisitor.h"
#include "ui_VisualizationTabWidget.h"

#include "Visualization/VisualizationZoneWidget.h"

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
}

VisualizationTabWidget::~VisualizationTabWidget()
{
    delete ui;
}

void VisualizationTabWidget::addZone(VisualizationZoneWidget *zoneWidget)
{
    this->layout()->addWidget(zoneWidget);
}

VisualizationZoneWidget *VisualizationTabWidget::createZone(std::shared_ptr<Variable> variable)
{
    auto zoneWidget = new VisualizationZoneWidget{defaultZoneName(*layout()), this};
    this->addZone(zoneWidget);

    // Creates a new graph into the zone
    zoneWidget->createGraph(variable);

    return zoneWidget;
}

void VisualizationTabWidget::removeZone(VisualizationZoneWidget *zone)
{
}

void VisualizationTabWidget::accept(IVisualizationWidgetVisitor *visitor)
{
    if (visitor) {
        visitor->visitEnter(this);

        // Apply visitor to zone children
        for (auto i = 0; i < layout()->count(); ++i) {
            if (auto item = layout()->itemAt(i)) {
                // Widgets different from zones are not visited (no action)
                if (auto visualizationZoneWidget
                    = dynamic_cast<VisualizationZoneWidget *>(item->widget())) {
                    visualizationZoneWidget->accept(visitor);
                }
            }
        }

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

QString VisualizationTabWidget::name() const
{
    return impl->m_Name;
}
