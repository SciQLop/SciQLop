#include "Settings/SqpSettingsGeneralWidget.h"

#include "Settings/SqpSettingsDefs.h"

#include "ui_SqpSettingsGeneralWidget.h"

SqpSettingsGeneralWidget::SqpSettingsGeneralWidget(QWidget *parent)
        : QWidget{parent}, ui{new Ui::SqpSettingsGeneralWidget}
{
    ui->setupUi(this);

    // Value limits
    ui->toleranceInitSpinBox->setMinimum(0.);
    ui->toleranceInitSpinBox->setMaximum(std::numeric_limits<double>::max());
    ui->toleranceUpdateSpinBox->setMinimum(0.);
    ui->toleranceUpdateSpinBox->setMaximum(std::numeric_limits<double>::max());
}

SqpSettingsGeneralWidget::~SqpSettingsGeneralWidget() noexcept
{
    delete ui;
}

void SqpSettingsGeneralWidget::loadSettings()
{
    QSettings settings{};

    auto loadTolerance = [&settings](const QString &key, double defaultValue) {
        // Tolerance is converted to percent
        auto toleranceValue = settings.value(key, defaultValue).toDouble();
        return toleranceValue * 100.;
    };

    ui->toleranceInitSpinBox->setValue(
        loadTolerance(GENERAL_TOLERANCE_AT_INIT_KEY, GENERAL_TOLERANCE_AT_INIT_DEFAULT_VALUE));
    ui->toleranceUpdateSpinBox->setValue(
        loadTolerance(GENERAL_TOLERANCE_AT_UPDATE_KEY, GENERAL_TOLERANCE_AT_UPDATE_DEFAULT_VALUE));
}

void SqpSettingsGeneralWidget::saveSettings() const
{
    QSettings settings{};

    auto saveTolerance = [&settings](const QString &key, double value) {
        // Tolerance is converted from percent
        settings.setValue(key, value * 0.01);
    };

    saveTolerance(GENERAL_TOLERANCE_AT_INIT_KEY, ui->toleranceInitSpinBox->value());
    saveTolerance(GENERAL_TOLERANCE_AT_UPDATE_KEY, ui->toleranceUpdateSpinBox->value());
}
