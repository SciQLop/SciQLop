#include "Variable/VariableMenuHeaderWidget.h"
#include "Variable/Variable.h"

#include <ui_VariableMenuHeaderWidget.h>

Q_LOGGING_CATEGORY(LOG_VariableMenuHeaderWidget, "VariableMenuHeaderWidget")

VariableMenuHeaderWidget::VariableMenuHeaderWidget(
    const QVector<std::shared_ptr<Variable> > &variables, QWidget *parent)
        : QWidget{parent}, ui{new Ui::VariableMenuHeaderWidget}
{
    ui->setupUi(this);

    // Generates label according to the state of the variables. The label contains :
    // - the variable name if there is only one variable in the list
    // - 'x variables' where x is the number of variables otherwise
    const auto nbVariables = variables.size();
    if (nbVariables == 1) {
        if (auto variable = variables.first()) {
            ui->label->setText(variable->name());
        }
        else {
            qCCritical(LOG_VariableMenuHeaderWidget())
                << tr("Can't get the name of the variable : variable is null");
        }
    }
    else if (nbVariables > 1) {
        ui->label->setText(tr("%1 variables").arg(nbVariables));
    }
    else {
        ui->label->setText(tr("No variable"));
    }
}

VariableMenuHeaderWidget::~VariableMenuHeaderWidget() noexcept
{
    delete ui;
}
