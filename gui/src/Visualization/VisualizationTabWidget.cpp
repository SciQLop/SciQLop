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

    // Widget is deleted when closed
    setAttribute(Qt::WA_DeleteOnClose);
}

VisualizationTabWidget::~VisualizationTabWidget()
{
    delete ui;
}

void VisualizationTabWidget::addZone(VisualizationZoneWidget *zoneWidget)
{
    tabLayout().addWidget(zoneWidget);
}

VisualizationZoneWidget *VisualizationTabWidget::createZone(std::shared_ptr<Variable> variable)
{
    auto zoneWidget = new VisualizationZoneWidget{defaultZoneName(tabLayout()), this};
    this->addZone(zoneWidget);

    // Creates a new graph into the zone
    zoneWidget->createGraph(variable);

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
    return *ui->scrollAreaWidgetContents->layout();
}
