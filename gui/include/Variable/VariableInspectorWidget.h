#ifndef SCIQLOP_VARIABLEINSPECTORWIDGET_H
#define SCIQLOP_VARIABLEINSPECTORWIDGET_H

#include <QMenu>
#include <QWidget>

#include <memory>

class Variable;

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

private slots:
    /// Slot called when right clicking on an variable in the table (displays a menu)
    void onTableMenuRequested(const QPoint &pos) noexcept;
};

#endif // SCIQLOP_VARIABLEINSPECTORWIDGET_H
