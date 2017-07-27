#ifndef SCIQLOP_SQPSETTINGSGENERALWIDGET_H
#define SCIQLOP_SQPSETTINGSGENERALWIDGET_H

#include <QWidget>

namespace Ui {
class SqpSettingsGeneralWidget;
} // Ui

/**
 * @brief The SqpSettingsGeneralWidget class represents the general settings of SciQlop
 */
class SqpSettingsGeneralWidget : public QWidget {
    Q_OBJECT

public:
    explicit SqpSettingsGeneralWidget(QWidget *parent = 0);
    virtual ~SqpSettingsGeneralWidget() noexcept;

private:
    Ui::SqpSettingsGeneralWidget *ui;
};

#endif // SCIQLOP_SQPSETTINGSGENERALWIDGET_H
