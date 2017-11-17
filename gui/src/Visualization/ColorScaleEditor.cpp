#include "Visualization/ColorScaleEditor.h"
#include "Visualization/SqpColorScale.h"

#include "ui_ColorScaleEditor.h"

namespace {

const auto GRADIENTS = QVariantMap{{"Candy", QCPColorGradient::gpCandy},
                                   {"Cold", QCPColorGradient::gpCold},
                                   {"Geography", QCPColorGradient::gpGeography},
                                   {"Grayscale", QCPColorGradient::gpGrayscale},
                                   {"Hot", QCPColorGradient::gpHot},
                                   {"Hues", QCPColorGradient::gpHues},
                                   {"Ion", QCPColorGradient::gpIon},
                                   {"Jet", QCPColorGradient::gpJet},
                                   {"Night", QCPColorGradient::gpNight},
                                   {"Polar", QCPColorGradient::gpPolar},
                                   {"Spectrum", QCPColorGradient::gpSpectrum},
                                   {"Thermal", QCPColorGradient::gpThermal}};

} // namespace

ColorScaleEditor::ColorScaleEditor(SqpColorScale &scale, QWidget *parent)
        : QDialog{parent},
          ui{new Ui::ColorScaleEditor},
          m_Scale{scale},
          m_ThresholdGroup{new QButtonGroup{this}}
{
    ui->setupUi(this);

    // Inits gradient combobox content
    for (auto it = GRADIENTS.begin(), end = GRADIENTS.end(); it != end; ++it) {
        ui->gradientComboBox->addItem(it.key(), it.value());
    }

    // Creates threshold group
    m_ThresholdGroup->addButton(ui->thresholdAutoButton);
    m_ThresholdGroup->addButton(ui->thresholdManualButton);

    // Inits min/max spinboxes' properties
    auto setSpinBoxProperties = [](auto &spinBox) {
        spinBox.setDecimals(3);
        spinBox.setMinimum(-std::numeric_limits<double>::max());
        spinBox.setMaximum(std::numeric_limits<double>::max());
    };
    setSpinBoxProperties(*ui->minSpinBox);
    setSpinBoxProperties(*ui->maxSpinBox);

    // Creates color scale preview
    m_PreviewScale = new QCPColorScale{ui->plot};
    m_PreviewScale->setType(QCPAxis::atTop);
    m_PreviewScale->setMinimumMargins(QMargins{5, 5, 5, 5});
    m_PreviewScale->axis()->setScaleType(QCPAxis::stLogarithmic);
    m_PreviewScale->axis()->setNumberPrecision(0);
    m_PreviewScale->axis()->setNumberFormat("eb");
    m_PreviewScale->axis()->setTicker(QSharedPointer<QCPAxisTickerLog>::create());
    m_PreviewScale->setGradient(QCPColorGradient{QCPColorGradient::gpJet});

    ui->plot->plotLayout()->clear();
    ui->plot->plotLayout()->insertRow(0);
    ui->plot->plotLayout()->addElement(0, 0, m_PreviewScale);

    // Inits connections
    connect(ui->gradientComboBox, SIGNAL(currentIndexChanged(int)), this, SLOT(updatePreview()));
    connect(ui->thresholdAutoButton, SIGNAL(toggled(bool)), this, SLOT(onThresholdChanged(bool)));
    connect(ui->thresholdManualButton, SIGNAL(toggled(bool)), this, SLOT(onThresholdChanged(bool)));
    connect(ui->minSpinBox, SIGNAL(editingFinished()), this, SLOT(onMinChanged()));
    connect(ui->maxSpinBox, SIGNAL(editingFinished()), this, SLOT(onMaxChanged()));

    // OK/cancel buttons
    connect(ui->okButton, SIGNAL(clicked(bool)), this, SLOT(accept()));
    connect(ui->cancelButton, SIGNAL(clicked(bool)), this, SLOT(reject()));

    // Loads color scale
    loadScale();
}

ColorScaleEditor::~ColorScaleEditor() noexcept
{
    delete ui;
}

void ColorScaleEditor::loadScale()
{
    // Gradient
    auto gradientPresetIndex = ui->gradientComboBox->findData(m_Scale.m_GradientPreset);
    ui->gradientComboBox->setCurrentIndex(gradientPresetIndex);

    // Threshold mode
    (m_Scale.m_AutomaticThreshold ? ui->thresholdAutoButton : ui->thresholdManualButton)
        ->setChecked(true);

    // Min/max
    auto qcpColorScale = m_Scale.m_Scale;
    auto range = qcpColorScale->dataRange();
    ui->minSpinBox->setValue(range.lower);
    ui->maxSpinBox->setValue(range.upper);

    updatePreview();
}

void ColorScaleEditor::saveScale()
{
    auto qcpColorScale = m_Scale.m_Scale;

    // Gradient
    auto gradientPreset
        = ui->gradientComboBox->currentData().value<QCPColorGradient::GradientPreset>();
    qcpColorScale->setGradient(gradientPreset);
    m_Scale.m_GradientPreset = gradientPreset;

    // Threshold mode
    m_Scale.m_AutomaticThreshold = ui->thresholdAutoButton->isChecked();

    // Min/max
    qcpColorScale->setDataRange(QCPRange{ui->minSpinBox->value(), ui->maxSpinBox->value()});
}

void ColorScaleEditor::accept()
{
    saveScale();
    QDialog::accept();
}

void ColorScaleEditor::onMaxChanged()
{
    // Ensures that max >= min
    auto maxValue = ui->maxSpinBox->value();
    if (maxValue < ui->minSpinBox->value()) {
        ui->minSpinBox->setValue(maxValue);
    }

    updatePreview();
}

void ColorScaleEditor::onMinChanged()
{
    // Ensures that min <= max
    auto minValue = ui->minSpinBox->value();
    if (minValue > ui->maxSpinBox->value()) {
        ui->maxSpinBox->setValue(minValue);
    }

    updatePreview();
}

void ColorScaleEditor::onThresholdChanged(bool checked)
{
    if (checked) {
        auto isAutomatic = ui->thresholdAutoButton == m_ThresholdGroup->checkedButton();

        ui->minSpinBox->setEnabled(!isAutomatic);
        ui->maxSpinBox->setEnabled(!isAutomatic);
    }
}

void ColorScaleEditor::updatePreview()
{
    m_PreviewScale->setDataRange(QCPRange{ui->minSpinBox->value(), ui->maxSpinBox->value()});
    m_PreviewScale->setGradient(
        ui->gradientComboBox->currentData().value<QCPColorGradient::GradientPreset>());

    ui->plot->replot();
}
