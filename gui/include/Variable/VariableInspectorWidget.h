#ifndef SCIQLOP_VARIABLEINSPECTORWIDGET_H
#define SCIQLOP_VARIABLEINSPECTORWIDGET_H

#include <QLoggingCategory>
#include <QMenu>
#include <QWidget>

#include <memory>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableInspectorWidget)

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

signals:
    /**
     * Signal emitted before a menu concerning variables is displayed. It is used for other widgets
     * to complete the menu.
     * @param tableMenu the menu to be completed
     * @param variables the variables concerned by the menu
     * @remarks To make the dynamic addition of menus work, the connections to this signal must be
     * in Qt :: DirectConnection
     */
    void tableMenuAboutToBeDisplayed(QMenu *tableMenu,
                                     const QVector<std::shared_ptr<Variable> > &variables);

private:
    Ui::VariableInspectorWidget *ui;

private slots:
    /// Slot called when right clicking on an variable in the table (displays a menu)
    void onTableMenuRequested(const QPoint &pos) noexcept;
};

#endif // SCIQLOP_VARIABLEINSPECTORWIDGET_H
