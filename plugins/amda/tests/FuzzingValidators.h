#ifndef SCIQLOP_FUZZINGVALIDATORS_H
#define SCIQLOP_FUZZINGVALIDATORS_H

#include <QLoggingCategory>

Q_DECLARE_LOGGING_CATEGORY(LOG_FuzzingValidators)

class VariableState;

/// Types of validators that can be defined
enum class FuzzingValidatorType {
    DATA, ///< Validates variable's data
    RANGE ///< Validates variable's range
};

/**
 * Struct that represents a validator. A validator checks if the state of a variable is valid at the
 * moment it is called during a fuzzing test
 */
struct IFuzzingValidator {
    virtual ~IFuzzingValidator() noexcept = default;

    /// Validates the variable's state passed in parameter
    virtual void validate(const VariableState &variableState) const = 0;
};

/// Factory of @sa IFuzzingValidator
struct FuzzingValidatorFactory {
    /// Creates a validator according to the type passed in parameter
    static std::unique_ptr<IFuzzingValidator> create(FuzzingValidatorType type);
};

#endif // SCIQLOP_FUZZINGVALIDATORS_H
