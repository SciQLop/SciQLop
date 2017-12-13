#include "FuzzingValidators.h"

#include <functional>

Q_LOGGING_CATEGORY(LOG_FuzzingValidators, "FuzzingValidators")

namespace {

/**
 * Default implementation of @sa IFuzzingValidator. This validator takes as parameter of its
 * construction a function of validation which is called in the validate() method
 */
class FuzzingValidator : public IFuzzingValidator {
public:
    /// Signature of a validation function
    using ValidationFunction = std::function<void(const VariableState &variableState)>;

    explicit FuzzingValidator(ValidationFunction fun) : m_Fun(std::move(fun)) {}

    void validate(const VariableState &variableState) const override { m_Fun(variableState); }

private:
    ValidationFunction m_Fun;
};

} // namespace
