#include "Visualization/VisualizationMultiZoneSelectionDialog.h"
#include "ui_VisualizationMultiZoneSelectionDialog.h"

#include "Common/DateUtils.h"
#include "Visualization/VisualizationSelectionZoneItem.h"

const auto DATETIME_FORMAT = QStringLiteral("yyyy/MM/dd hh:mm:ss");

struct VisualizationMultiZoneSelectionDialog::VisualizationMultiZoneSelectionDialogPrivate {
    QVector<VisualizationSelectionZoneItem *> m_Zones;
};

VisualizationMultiZoneSelectionDialog::VisualizationMultiZoneSelectionDialog(QWidget *parent)
        : QDialog(parent, Qt::Tool),
          ui(new Ui::VisualizationMultiZoneSelectionDialog),
          impl{spimpl::make_unique_impl<VisualizationMultiZoneSelectionDialogPrivate>()}
{
    ui->setupUi(this);

    connect(ui->buttonBox, &QDialogButtonBox::accepted, this,
            &VisualizationMultiZoneSelectionDialog::accept);
    connect(ui->buttonBox, &QDialogButtonBox::rejected, this,
            &VisualizationMultiZoneSelectionDialog::reject);
}

VisualizationMultiZoneSelectionDialog::~VisualizationMultiZoneSelectionDialog()
{
    delete ui;
}

void VisualizationMultiZoneSelectionDialog::setZones(
    const QVector<VisualizationSelectionZoneItem *> &zones)
{
    impl->m_Zones = zones;

    // Sorts the zones to display them in temporal order
    std::sort(impl->m_Zones.begin(), impl->m_Zones.end(), [](auto zone1, auto zone2) {
        return zone1->range().m_TStart < zone2->range().m_TStart;
    });

    // Adds the zones in the listwidget
    for (auto zone : impl->m_Zones) {
        auto name = zone->name();
        if (!name.isEmpty()) {
            name += tr(": ");
        }

        auto range = zone->range();
        name += DateUtils::dateTime(range.m_TStart).toString(DATETIME_FORMAT);
        name += " - ";
        name += DateUtils::dateTime(range.m_TEnd).toString(DATETIME_FORMAT);

        auto item = new QListWidgetItem(name, ui->listWidget);
        item->setSelected(zone->selected());
    }
}

QMap<VisualizationSelectionZoneItem *, bool>
VisualizationMultiZoneSelectionDialog::selectedZones() const
{
    QMap<VisualizationSelectionZoneItem *, bool> selectedZones;

    for (auto i = 0; i < ui->listWidget->count(); ++i) {
        auto item = ui->listWidget->item(i);
        selectedZones[impl->m_Zones[i]] = item->isSelected();
    }

    return selectedZones;
}
