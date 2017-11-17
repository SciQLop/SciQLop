#include "Visualization/ColorScaleEditor.h"

#include "ui_ColorScaleEditor.h"

ColorScaleEditor::ColorScaleEditor(QWidget *parent)
        : QDialog{parent}, ui{new Ui::ColorScaleEditor}, m_ThresholdGroup{new QButtonGroup{this}}
{
    ui->setupUi(this);
    // Creates threshold group
    m_ThresholdGroup->addButton(ui->thresholdAutoButton);
    m_ThresholdGroup->addButton(ui->thresholdManualButton);

    // Inits connections
    connect(ui->thresholdAutoButton, SIGNAL(toggled(bool)), this, SLOT(onThresholdChanged(bool)));
    connect(ui->thresholdManualButton, SIGNAL(toggled(bool)), this, SLOT(onThresholdChanged(bool)));

    // First update
    onThresholdChanged(true);
}

ColorScaleEditor::~ColorScaleEditor() noexcept
{
    delete ui;
}
void ColorScaleEditor::onThresholdChanged(bool checked)
{
    if (checked) {
        auto isAutomatic = ui->thresholdAutoButton == m_ThresholdGroup->checkedButton();

        ui->minSpinBox->setEnabled(!isAutomatic);
        ui->maxSpinBox->setEnabled(!isAutomatic);
    }
}

