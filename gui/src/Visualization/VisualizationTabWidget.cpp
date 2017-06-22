#include "Visualization/VisualizationTabWidget.h"
#include "ui_VisualizationTabWidget.h"

#include "Visualization/VisualizationZoneWidget.h"

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

VisualizationZoneWidget *VisualizationTabWidget::createZone()
{
    auto zoneWidget = new VisualizationZoneWidget{this};
    this->addZone(zoneWidget);

    return zoneWidget;
}

void VisualizationTabWidget::removeZone(VisualizationZoneWidget *zone)
{
}

void VisualizationTabWidget::accept(IVisualizationWidget *visitor)
{
    // TODO: manage the visitor
}

void VisualizationTabWidget::close()
{
    // The main view cannot be directly closed.
    return;
}

QString VisualizationTabWidget::name() const
{
    return impl->m_Name;
}
