#include "Variable/RenameVariableDialog.h"

#include <ui_RenameVariableDialog.h>

RenameVariableDialog::RenameVariableDialog(const QString &defaultName,
                                           const QVector<QString> &forbiddenNames, QWidget *parent)
        : QDialog{parent},
          ui{new Ui::RenameVariableDialog},
          m_DefaultName{defaultName},
          m_ForbiddenNames{forbiddenNames}
{
    ui->setupUi(this);

    connect(ui->nameLineEdit, &QLineEdit::textChanged, [this]() { ui->errorLabel->hide(); });

    ui->nameLineEdit->setText(defaultName);
    ui->nameLineEdit->selectAll();
    ui->nameLineEdit->setFocus();
}

RenameVariableDialog::~RenameVariableDialog() noexcept
{
    delete ui;
}

QString RenameVariableDialog::name() const noexcept
{
    return ui->nameLineEdit->text();
}

void RenameVariableDialog::accept()
{
    auto invalidateInput = [this](const auto &error) {
        ui->nameLineEdit->selectAll();
        ui->nameLineEdit->setFocus();
        ui->errorLabel->setText(error);
        ui->errorLabel->show();
    };

    // Empty name
    auto name = ui->nameLineEdit->text();
    if (name.isEmpty()) {
        invalidateInput(tr("A variable name must be specified"));
        return;
    }

    // Same name when opening dialog
    if (name.compare(m_DefaultName, Qt::CaseInsensitive) == 0) {
        reject();
        return;
    }

    // Forbidden name
    auto isForbidden
        = [&name](const auto &it) { return name.compare(it, Qt::CaseInsensitive) == 0; };
    if (std::any_of(m_ForbiddenNames.cbegin(), m_ForbiddenNames.cend(), isForbidden)) {
        invalidateInput(tr("'%1' is already used").arg(name));
        return;
    }

    // Valid name
    QDialog::accept();
}
