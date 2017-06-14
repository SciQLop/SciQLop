#ifndef SCIQLOP_VARIABLEMODEL_H
#define SCIQLOP_VARIABLEMODEL_H

#include <Common/spimpl.h>

#include <QLoggingCategory>

Q_DECLARE_LOGGING_CATEGORY(LOG_VariableModel)

class Variable;

/**
 * @brief The VariableModel class aims to hold the variables that have been created in SciQlop
 */
class VariableModel {
public:
    explicit VariableModel();

    /**
     * Creates a new variable in the model
     * @param name the name of the new variable
     * @return the variable if it was created successfully, nullptr otherwise
     */
    Variable *createVariable(const QString &name) noexcept;

private:
    class VariableModelPrivate;
    spimpl::unique_impl_ptr<VariableModelPrivate> impl;
};

#endif // SCIQLOP_VARIABLEMODEL_H
