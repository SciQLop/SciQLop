#ifndef SCIQLOP_VARIABLEINSPECTORWIDGET_H
#define SCIQLOP_VARIABLEINSPECTORWIDGET_H

#include <QWidget>

namespace Ui {
class VariableInspectorWidget;
} // Ui

/**
 * @brief The VariableInspectorWidget class representes represents the variable inspector, from
 * which it is possible to view the loaded variables, handle them or trigger their display in
 * visualization
 */
class VariableInspectorWidget : public QWidget {
    Q_OBJECT

public:
    explicit VariableInspectorWidget(QWidget *parent = 0);
    virtual ~VariableInspectorWidget();

private:
    Ui::VariableInspectorWidget *ui;
};

#endif // SCIQLOP_VARIABLEINSPECTORWIDGET_H
