#ifndef SCIQLOP_VARIABLEMENUHEADERWIDGET_H
#define SCIQLOP_VARIABLEMENUHEADERWIDGET_H

#include <QLoggingCategory>
#include <QWidget>

#include <memory>

namespace Ui
{
class VariableMenuHeaderWidget;
} // Ui

class Variable2;

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableMenuHeaderWidget)

/**
 * @brief The VariableMenuHeaderWidget class represents the widget used as a header of a menu in the
 * variable inspector
 * @sa VariableInspectorWidget
 */
class VariableMenuHeaderWidget : public QWidget
{
public:
    /**
     * Ctor
     * @param variables the list of variables used to generate the header
     * @param parent the parent widget
     */
    explicit VariableMenuHeaderWidget(
        const QVector<std::shared_ptr<Variable2>>& variables, QWidget* parent = 0);
    virtual ~VariableMenuHeaderWidget() noexcept;

private:
    Ui::VariableMenuHeaderWidget* ui;
};

#endif // SCIQLOP_VARIABLEMENUHEADERWIDGET_H
