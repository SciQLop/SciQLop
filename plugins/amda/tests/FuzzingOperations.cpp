#include "FuzzingOperations.h"
#include "FuzzingUtils.h"

#include <Data/IDataProvider.h>

#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <QUuid>

#include <functional>

Q_LOGGING_CATEGORY(LOG_FuzzingOperations, "FuzzingOperations")

namespace {

struct CreateOperation : public IFuzzingOperation {
    bool canExecute(const VariableState &variableState) const override
    {
        // A variable can be created only if it doesn't exist yet
        return variableState.m_Variable == nullptr;
    }

    void execute(VariableState &variableState, VariableController &variableController,
                 const Properties &properties) const override
    {
        // Retrieves metadata pool from properties, and choose one of the metadata entries to
        // associate it with the variable
        auto metaDataPool = properties.value(METADATA_POOL_PROPERTY).value<MetadataPool>();
        auto variableMetadata = RandomGenerator::instance().randomChoice(metaDataPool);

        // Retrieves provider
        auto variableProvider
            = properties.value(PROVIDER_PROPERTY).value<std::shared_ptr<IDataProvider> >();

        auto variableName = QString{"Var_%1"}.arg(QUuid::createUuid().toString());
        qCInfo(LOG_FuzzingOperations()).noquote()
            << "Creating variable" << variableName << "(metadata:" << variableMetadata << ")...";

        auto newVariable
            = variableController.createVariable(variableName, variableMetadata, variableProvider);

        // Updates variable's state
        variableState.m_Range = properties.value(INITIAL_RANGE_PROPERTY).value<SqpRange>();
        std::swap(variableState.m_Variable, newVariable);
    }
};

struct DeleteOperation : public IFuzzingOperation {
    bool canExecute(const VariableState &variableState) const override
    {
        // A variable can be delete only if it exists
        return variableState.m_Variable != nullptr;
    }

    void execute(VariableState &variableState, VariableController &variableController,
                 const Properties &properties) const override
    {
        Q_UNUSED(properties);

        qCInfo(LOG_FuzzingOperations()).noquote()
            << "Deleting variable" << variableState.m_Variable->name() << "...";
        variableController.deleteVariable(variableState.m_Variable);

        // Updates variable's state
        variableState.m_Range = INVALID_RANGE;
        variableState.m_Variable = nullptr;
    }
};

/**
 * Defines a move operation through a range.
 *
 * A move operation is determined by three functions:
 * - Two 'move' functions, used to indicate in which direction the beginning and the end of a range
 * are going during the operation. These functions will be:
 * -- {<- / <-} for pan left
 * -- {-> / ->} for pan right
 * -- {-> / <-} for zoom in
 * -- {<- / ->} for zoom out
 * - One 'max move' functions, used to compute the max delta at which the operation can move a
 * range, according to a max range. For exemple, for a range of {1, 5} and a max range of {0, 10},
 * max deltas will be:
 * -- {0, 4} for pan left
 * -- {6, 10} for pan right
 * -- {3, 3} for zoom in
 * -- {0, 6} for zoom out (same spacing left and right)
 */
struct MoveOperation : public IFuzzingOperation {
    using MoveFunction = std::function<double(double currentValue, double maxValue)>;
    using MaxMoveFunction = std::function<double(const SqpRange &range, const SqpRange &maxRange)>;

    explicit MoveOperation(MoveFunction rangeStartMoveFun, MoveFunction rangeEndMoveFun,
                           MaxMoveFunction maxMoveFun,
                           const QString &label = QStringLiteral("Move operation"))
            : m_RangeStartMoveFun{std::move(rangeStartMoveFun)},
              m_RangeEndMoveFun{std::move(rangeEndMoveFun)},
              m_MaxMoveFun{std::move(maxMoveFun)},
              m_Label{label}
    {
    }

    bool canExecute(const VariableState &variableState) const override
    {
        return variableState.m_Variable != nullptr;
    }

    void execute(VariableState &variableState, VariableController &variableController,
                 const Properties &properties) const override
    {
        auto variable = variableState.m_Variable;

        // Gets the max range defined
        auto maxRange = properties.value(MAX_RANGE_PROPERTY, QVariant::fromValue(INVALID_RANGE))
                            .value<SqpRange>();
        auto variableRange = variable->range();

        if (maxRange == INVALID_RANGE || variableRange.m_TStart < maxRange.m_TStart
            || variableRange.m_TEnd > maxRange.m_TEnd) {
            qCWarning(LOG_FuzzingOperations()) << "Can't execute operation: invalid max range";
            return;
        }

        // Computes the max delta at which the variable can move, up to the limits of the max range
        auto deltaMax = m_MaxMoveFun(variable->range(), maxRange);

        // Generates random delta that will be used to move variable
        auto delta = RandomGenerator::instance().generateDouble(0, deltaMax);

        // Moves variable to its new range
        auto newVariableRange = SqpRange{m_RangeStartMoveFun(variableRange.m_TStart, delta),
                                         m_RangeEndMoveFun(variableRange.m_TEnd, delta)};
        qCInfo(LOG_FuzzingOperations()).noquote()
            << "Performing" << m_Label << "on" << variable->name() << "(from" << variableRange
            << "to" << newVariableRange << ")...";
        variableController.onRequestDataLoading({variable}, newVariableRange, false);

        // Updates variable's state
        variableState.m_Range = newVariableRange;
    }

    MoveFunction m_RangeStartMoveFun;
    MoveFunction m_RangeEndMoveFun;
    MaxMoveFunction m_MaxMoveFun;
    QString m_Label;
};

struct UnknownOperation : public IFuzzingOperation {
    bool canExecute(const VariableState &variableState) const override
    {
        Q_UNUSED(variableState);
        return false;
    }

    void execute(VariableState &variableState, VariableController &variableController,
                 const Properties &properties) const override
    {
        Q_UNUSED(variableState);
        Q_UNUSED(variableController);
        Q_UNUSED(properties);
        // Does nothing
    }
};

} // namespace

std::unique_ptr<IFuzzingOperation> FuzzingOperationFactory::create(FuzzingOperationType type)
{
    switch (type) {
        case FuzzingOperationType::CREATE:
            return std::make_unique<CreateOperation>();
        case FuzzingOperationType::DELETE:
            return std::make_unique<DeleteOperation>();
        case FuzzingOperationType::PAN_LEFT:
            return std::make_unique<MoveOperation>(
                std::minus<double>(), std::minus<double>(),
                [](const SqpRange &range, const SqpRange &maxRange) {
                    return range.m_TStart - maxRange.m_TStart;
                },
                QStringLiteral("Pan left operation"));
        case FuzzingOperationType::PAN_RIGHT:
            return std::make_unique<MoveOperation>(
                std::plus<double>(), std::plus<double>(),
                [](const SqpRange &range, const SqpRange &maxRange) {
                    return maxRange.m_TEnd - range.m_TEnd;
                },
                QStringLiteral("Pan right operation"));
        case FuzzingOperationType::ZOOM_IN:
            return std::make_unique<MoveOperation>(
                std::plus<double>(), std::minus<double>(),
                [](const SqpRange &range, const SqpRange &maxRange) {
                    Q_UNUSED(maxRange)
                    return range.m_TEnd - (range.m_TStart + range.m_TEnd) / 2.;
                },
                QStringLiteral("Zoom in operation"));
        case FuzzingOperationType::ZOOM_OUT:
            return std::make_unique<MoveOperation>(
                std::minus<double>(), std::plus<double>(),
                [](const SqpRange &range, const SqpRange &maxRange) {
                    return std::min(range.m_TStart - maxRange.m_TStart,
                                    maxRange.m_TEnd - range.m_TEnd);
                },
                QStringLiteral("Zoom out operation"));
        default:
            // Default case returns unknown operation
            break;
    }

    return std::make_unique<UnknownOperation>();
}
