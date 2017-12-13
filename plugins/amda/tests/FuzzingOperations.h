#ifndef SCIQLOP_FUZZINGOPERATIONS_H
#define SCIQLOP_FUZZINGOPERATIONS_H

#include "FuzzingDefs.h"

#include <memory>
#include <set>

#include <QLoggingCategory>
#include <QMetaType>

Q_DECLARE_LOGGING_CATEGORY(LOG_FuzzingOperations)

class VariableController;

/**
 * Enumeration of types of existing fuzzing operations
 */
enum class FuzzingOperationType { CREATE, PAN_LEFT, PAN_RIGHT, ZOOM_IN, ZOOM_OUT };

/// Interface that represents an operation that can be executed during a fuzzing test
struct IFuzzingOperation {
    virtual ~IFuzzingOperation() noexcept = default;

    /// Checks if the operation can be executed according to the current variable state passed in
    /// parameter
    virtual bool canExecute(const VariableState &variableState) const = 0;
    /// Executes the operation on the variable state passed in parameter
    /// @param variableState the variable state on which to execute the operation
    /// @param variableController the controller associated to the operation
    /// @param properties properties that can be used to configure the operation
    /// @remarks variableState is passed as a reference because, according to the operation, it can
    /// be
    /// modified (in/out parameter)
    virtual void execute(VariableState &variableState, VariableController &variableController,
                         const Properties &properties = {}) const = 0;
};

/// Factory of @sa IFuzzingOperation
struct FuzzingOperationFactory {
    /// Creates a fuzzing operation from a type
    static std::unique_ptr<IFuzzingOperation> create(FuzzingOperationType type);
};

using WeightedOperationsTypes = std::map<FuzzingOperationType, double>;
Q_DECLARE_METATYPE(WeightedOperationsTypes)

#endif // SCIQLOP_FUZZINGOPERATIONS_H
