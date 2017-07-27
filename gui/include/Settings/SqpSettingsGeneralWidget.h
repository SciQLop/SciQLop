#ifndef SCIQLOP_SQPSETTINGSGENERALWIDGET_H
#define SCIQLOP_SQPSETTINGSGENERALWIDGET_H

#include "Settings/ISqpSettingsBindable.h"

#include <QWidget>

namespace Ui {
class SqpSettingsGeneralWidget;
} // Ui

/**
 * @brief The SqpSettingsGeneralWidget class represents the general settings of SciQlop
 */
class SqpSettingsGeneralWidget : public QWidget, public ISqpSettingsBindable {
    Q_OBJECT

public:
    explicit SqpSettingsGeneralWidget(QWidget *parent = 0);
    virtual ~SqpSettingsGeneralWidget() noexcept;

    /// @sa ISqpSettingsBindable::loadSettings()
    void loadSettings() override final;

    /// @sa ISqpSettingsBindable::saveSettings()
    void saveSettings() const override final;

private:
    Ui::SqpSettingsGeneralWidget *ui;
};

#endif // SCIQLOP_SQPSETTINGSGENERALWIDGET_H
