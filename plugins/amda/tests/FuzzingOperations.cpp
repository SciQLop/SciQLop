#include "FuzzingOperations.h"

#include <Variable/Variable.h>
#include <Variable/VariableController.h>

Q_LOGGING_CATEGORY(LOG_FuzzingOperations, "FuzzingOperations")

namespace {

struct CreateOperation : public IFuzzingOperation {
    bool canExecute(std::shared_ptr<Variable> variable) const override {
        /// @todo: complete
        return false;
    }

    void execute(std::shared_ptr<Variable>& variable, VariableController &variableController, const Properties &properties) const override{
        /// @todo: complete
    }
};

struct UnknownOperation : public IFuzzingOperation {
    bool canExecute(std::shared_ptr<Variable> variable) const override {
        Q_UNUSED(variable);
        return false;
    }

    void execute(std::shared_ptr<Variable>& variable, VariableController &variableController, const Properties &properties) const override{
        Q_UNUSED(variable);
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
    default:
        // Default case returns unknown operation
        break;
    }

    return std::make_unique<UnknownOperation>();
}
