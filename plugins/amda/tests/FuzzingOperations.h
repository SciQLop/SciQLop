#ifndef SCIQLOP_FUZZINGOPERATIONS_H
#define SCIQLOP_FUZZINGOPERATIONS_H

#include "FuzzingDefs.h"

#include <memory>
#include <set>

#include <QLoggingCategory>
#include <QMetaType>
#include <Variable/VariableController2.h>

Q_DECLARE_LOGGING_CATEGORY(LOG_FuzzingOperations)

class VariableController;

/**
 * Enumeration of types of existing fuzzing operations
 */
enum class FuzzingOperationType {
    CREATE,
    DELETE,
    PAN_LEFT,
    PAN_RIGHT,
    ZOOM_IN,
    ZOOM_OUT,
    SYNCHRONIZE,
    DESYNCHRONIZE
};

/// Interface that represents an operation that can be executed during a fuzzing test
struct IFuzzingOperation {
    virtual ~IFuzzingOperation() noexcept = default;

    /// Checks if the operation can be executed according to the current test's state for the
    /// variable passed in parameter
    virtual bool canExecute(VariableId variableId, const FuzzingState &fuzzingState) const = 0;
    /// Executes the operation on the variable for which its identifier is passed in parameter
    /// @param variableId the variable identifier
    /// @param fuzzingState the current test's state on which to find the variable and execute the
    /// operation
    /// @param variableController the controller associated to the operation
    /// @param properties properties that can be used to configure the operation
    /// @remarks fuzzingState is passed as a reference because, according to the operation, it can
    /// be modified (in/out parameter)
    virtual void execute(VariableId variableId, FuzzingState &fuzzingState,
                         VariableController2 &variableController,
                         const Properties &properties = {}) const = 0;
};

/// Factory of @sa IFuzzingOperation
struct FuzzingOperationFactory {
    /// Creates a fuzzing operation from a type
    static std::unique_ptr<IFuzzingOperation> create(FuzzingOperationType type);
};

#endif // SCIQLOP_FUZZINGOPERATIONS_H
