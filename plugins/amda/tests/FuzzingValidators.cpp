#include "FuzzingValidators.h"
#include <Variable/Variable.h>

#include <QTest>

#include <functional>

Q_LOGGING_CATEGORY(LOG_FuzzingValidators, "FuzzingValidators")

namespace {

// ////////////// //
// DATA VALIDATOR //
// ////////////// //

/// Singleton used to validate data of a variable
class DataValidatorHelper {
public:
    /// @return the single instance of the helper
    static DataValidatorHelper &instance();
    virtual ~DataValidatorHelper() noexcept = default;

    virtual void validate(const VariableState &variableState) const = 0;
};

/**
 * Default implementation of @sa DataValidatorHelper
 */
class DefaultDataValidatorHelper : public DataValidatorHelper {
public:
    void validate(const VariableState &variableState) const override
    {
        Q_UNUSED(variableState);
        qCWarning(LOG_FuzzingValidators()).noquote() << "Checking variable's data... WARN: no data "
                                                        "verification is available for this server";
    }
};

/**
 * Implementation of @sa DataValidatorHelper for the local AMDA server
 */
class LocalhostServerDataValidatorHelper : public DataValidatorHelper {
public:
    void validate(const VariableState &variableState) const override
    {
        /// @todo: complete
    }
};

/// Creates the @sa DataValidatorHelper according to the server passed in parameter
std::unique_ptr<DataValidatorHelper> createDataValidatorInstance(const QString &server)
{
    if (server == QString{"localhost"}) {
        return std::make_unique<LocalhostServerDataValidatorHelper>();
    }
    else {
        return std::make_unique<DefaultDataValidatorHelper>();
    }
}

DataValidatorHelper &DataValidatorHelper::instance()
{
    // Creates instance depending on the SCIQLOP_AMDA_SERVER value at compile time
    static auto instance = createDataValidatorInstance(SCIQLOP_AMDA_SERVER);
    return *instance;
}

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
                DataValidatorHelper::instance().validate(variableState);
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
