#ifndef SCIQLOP_RENAMEVARIABLEDIALOG_H
#define SCIQLOP_RENAMEVARIABLEDIALOG_H

#include <QDialog>

namespace Ui {
class RenameVariableDialog;
} // Ui

/**
 * @brief The RenameVariableDialog class represents the dialog to rename a variable
 */
class RenameVariableDialog : public QDialog {
    Q_OBJECT
public:
    explicit RenameVariableDialog(const QString &defaultName,
                                  const QVector<QString> &forbiddenNames,
                                  QWidget *parent = nullptr);
    virtual ~RenameVariableDialog() noexcept;

    QString name() const noexcept;

public slots:
    void accept() override;

private:
    Ui::RenameVariableDialog *ui;
    QString m_DefaultName;
    QVector<QString> m_ForbiddenNames;
};

#endif // SCIQLOP_RENAMEVARIABLEDIALOG_H
