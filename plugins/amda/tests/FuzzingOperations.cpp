#include "FuzzingOperations.h"
#include "FuzzingUtils.h"

#include <Data/IDataProvider.h>

#include <Variable/Variable.h>
#include <Variable/VariableController.h>

#include <QUuid>

Q_LOGGING_CATEGORY(LOG_FuzzingOperations, "FuzzingOperations")

namespace {

struct CreateOperation : public IFuzzingOperation {
    bool canExecute(std::shared_ptr<Variable> variable) const override {
        // A variable can be created only if it doesn't exist yet
        return variable == nullptr;
    }

    void execute(std::shared_ptr<Variable>& variable, VariableController &variableController, const Properties &properties) const override{
        // Retrieves metadata pool from properties, and choose one of the metadata entries to associate it with the variable
        auto metaDataPool = properties.value(METADATA_POOL_PROPERTY).value<MetadataPool>();
        auto variableMetadata = RandomGenerator::instance().randomChoice(metaDataPool);

        // Retrieves provider
        auto variableProvider = properties.value(PROVIDER_PROPERTY).value<std::shared_ptr<IDataProvider>>();

        auto variableName = QString{"Var_%1"}.arg(QUuid::createUuid().toString());
        qCInfo(LOG_FuzzingOperations()) << "Creating variable" << variableName << "(metadata:" << variableMetadata << ")";

        auto newVariable = variableController.createVariable(variableName, variableMetadata, variableProvider);
        std::swap(variable, newVariable);
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
