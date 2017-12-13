#include "FuzzingValidators.h"

#include <QTest>

#include <functional>

Q_LOGGING_CATEGORY(LOG_FuzzingValidators, "FuzzingValidators")

namespace {

// /////////////// //
// RANGE VALIDATOR //
// /////////////// //

/**
 * Checks that a range of a variable matches the expected range passed as a parameter
 * @param variable the variable for which to check the range
 * @param expectedRange the expected range
 * @param getVariableRangeFun the function to retrieve the range from the variable
 * @remarks if the variable is null, checks that the expected range is the invalid range
 */
void validateRange(std::shared_ptr<Variable> variable, const SqpRange &expectedRange,
                   std::function<SqpRange(const Variable &)> getVariableRangeFun)
{
    auto compare = [](const auto &range, const auto &expectedRange, const auto &message) {
        if (range == expectedRange) {
            qCInfo(LOG_FuzzingValidators()).noquote() << message << "OK";
        }
        else {
            qCInfo(LOG_FuzzingValidators()).noquote()
                << message << "FAIL (current range:" << range
                << ", expected range:" << expectedRange << ")";
            QFAIL("");
        }
    };

    if (variable) {
        compare(getVariableRangeFun(*variable), expectedRange, "Checking variable's range...");
    }
    else {
        compare(INVALID_RANGE, expectedRange, "Checking that there is no range set...");
    }
}

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

std::unique_ptr<IFuzzingValidator> FuzzingValidatorFactory::create(FuzzingValidatorType type)
{
    switch (type) {
        case FuzzingValidatorType::DATA:
            return std::make_unique<FuzzingValidator>([](const VariableState &variableState) {
                /// @todo: complete
            });
        case FuzzingValidatorType::RANGE:
            return std::make_unique<FuzzingValidator>([](const VariableState &variableState) {
                auto getVariableRange = [](const Variable &variable) { return variable.range(); };
                validateRange(variableState.m_Variable, variableState.m_Range, getVariableRange);
            });
        default:
            // Default case returns invalid validator
            break;
    }

    // Invalid validator
    return std::make_unique<FuzzingValidator>(
        [](const VariableState &) { QFAIL("Invalid validator"); });
}
