#include "FuzzingValidators.h"
#include "FuzzingDefs.h"

#include <Data/DataSeries.h>
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

/// Data resolution in local server's files
const auto LOCALHOST_SERVER_RESOLUTION = 4;
/**
 * Implementation of @sa DataValidatorHelper for the local AMDA server
 */
class LocalhostServerDataValidatorHelper : public DataValidatorHelper {
public:
    void validate(const VariableState &variableState) const override
    {
        // Don't check data for null variable
        if (!variableState.m_Variable || variableState.m_Range == INVALID_RANGE) {
            return;
        }

        auto message = "Checking variable's data...";
        auto toDateString = [](double value) { return DateUtils::dateTime(value).toString(); };

        // Checks that data are defined
        auto variableDataSeries = variableState.m_Variable->dataSeries();
        if (variableDataSeries == nullptr && variableState.m_Range != INVALID_RANGE) {
            qCInfo(LOG_FuzzingValidators()).noquote()
                << message << "FAIL: the variable has no data while a range is defined";
            QFAIL("");
        }

        auto dataIts = variableDataSeries->xAxisRange(variableState.m_Range.m_TStart,
                                                      variableState.m_Range.m_TEnd);

        // Checks that the data are well defined in the range:
        // - there is at least one data
        // - the data are consistent (no data holes)
        if (std::distance(dataIts.first, dataIts.second) == 0) {
            qCInfo(LOG_FuzzingValidators()).noquote()
                << message << "FAIL: the variable has no data";
            QFAIL("");
        }

        auto firstXAxisData = dataIts.first->x();
        auto lastXAxisData = (dataIts.second - 1)->x();

        if (std::abs(firstXAxisData - variableState.m_Range.m_TStart) > LOCALHOST_SERVER_RESOLUTION
            || std::abs(lastXAxisData - variableState.m_Range.m_TEnd)
                   > LOCALHOST_SERVER_RESOLUTION) {
            qCInfo(LOG_FuzzingValidators()).noquote()
                << message << "FAIL: the data in the defined range are inconsistent (data hole "
                              "found at the beginning or the end)";
            QFAIL("");
        }

        auto dataHoleIt = std::adjacent_find(
            dataIts.first, dataIts.second, [](const auto &it1, const auto &it2) {
                /// @todo: validate resolution
                return std::abs(it1.x() - it2.x()) > 2 * (LOCALHOST_SERVER_RESOLUTION - 1);
            });

        if (dataHoleIt != dataIts.second) {
            qCInfo(LOG_FuzzingValidators()).noquote()
                << message << "FAIL: the data in the defined range are inconsistent (data hole "
                              "found between times "
                << toDateString(dataHoleIt->x()) << "and " << toDateString((dataHoleIt + 1)->x())
                << ")";
            QFAIL("");
        }

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
