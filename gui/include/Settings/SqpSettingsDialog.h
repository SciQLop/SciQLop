#ifndef SCIQLOP_SQPSETTINGSDIALOG_H
#define SCIQLOP_SQPSETTINGSDIALOG_H

#include "Settings/ISqpSettingsBindable.h"

#include <QDialog>

namespace Ui {
class SqpSettingsDialog;
} // Ui

/**
 * @brief The SqpSettingsDialog class represents the dialog in which the parameters of SciQlop are
 * set
 */
class SqpSettingsDialog : public QDialog {
    Q_OBJECT

public:
    explicit SqpSettingsDialog(QWidget *parent = 0);
    virtual ~SqpSettingsDialog() noexcept;

private:
    Ui::SqpSettingsDialog *ui;
};

#endif // SCIQLOP_SQPSETTINGSDIALOG_H
