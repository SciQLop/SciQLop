#ifndef SCIQLOP_VARIABLECONTROLLER_H
#define SCIQLOP_VARIABLECONTROLLER_H

#include <QLoggingCategory>
#include <QObject>

#include <Common/spimpl.h>

class Variable;
class VariableModel;

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableController)

/**
 * @brief The VariableController class aims to handle the variables in SciQlop.
 */
class VariableController : public QObject {
    Q_OBJECT
public:
    explicit VariableController(QObject *parent = 0);
    virtual ~VariableController();

    /**
     * Creates a new variable
     * @param name the name of the new variable
     * @return the variable if it was created successfully, nullptr otherwise
     */
    Variable *createVariable(const QString &name) noexcept;

    VariableModel *variableModel() noexcept;

public slots:
    void initialize();
    void finalize();

private:
    void waitForFinish();

    class VariableControllerPrivate;
    spimpl::unique_impl_ptr<VariableControllerPrivate> impl;
};

#endif // SCIQLOP_VARIABLECONTROLLER_H
