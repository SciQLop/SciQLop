#ifndef SCIQLOP_FUZZINGOPERATIONS_H
#define SCIQLOP_FUZZINGOPERATIONS_H

#include "FuzzingDefs.h"

#include <memory>
#include <set>

#include <QLoggingCategory>
#include <QMetaType>

Q_DECLARE_LOGGING_CATEGORY(LOG_FuzzingOperations)

class Variable;
class VariableController;

/**
 * Enumeration of types of existing fuzzing operations
 */
enum class FuzzingOperationType {
    CREATE
};

/// Interface that represents an operation that can be executed during a fuzzing test
struct IFuzzingOperation {
    virtual ~IFuzzingOperation() noexcept = default;

    /// Checks if the operation can be executed according to the current state of the variable passed in parameter
    virtual bool canExecute(std::shared_ptr<Variable> variable) const = 0;
    /// Executes the operation on the variable passed in parameter
    /// @param variable the variable on which to execute the operation
    /// @param variableController the controller associated to the operation
    /// @param properties properties that can be used to configure the operation
    /// @remarks variable is passed as a reference because, according to the operation, it can be modified (in/out parameter)
    virtual void execute(std::shared_ptr<Variable> &variable, VariableController& variableController, const Properties& properties = {}) const = 0;
};

/// Factory of @sa IFuzzingOperation
struct FuzzingOperationFactory {
    /// Creates a fuzzing operation from a type
    static std::unique_ptr<IFuzzingOperation> create(FuzzingOperationType type);
};

using OperationsTypes = std::set<FuzzingOperationType>;
Q_DECLARE_METATYPE(OperationsTypes)

#endif // SCIQLOP_FUZZINGOPERATIONS_H
