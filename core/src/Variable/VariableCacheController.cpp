#include "Variable/VariableCacheController.h"

#include "Variable/Variable.h"
#include <unordered_map>

struct VariableCacheController::VariableCacheControllerPrivate {

    std::unordered_map<std::shared_ptr<Variable>, std::list<SqpDateTime> >
        m_VariableToSqpDateTimeListMap;
};


VariableCacheController::VariableCacheController(QObject *parent)
        : QObject(parent), impl{spimpl::make_unique_impl<VariableCacheControllerPrivate>()}
{
}

void VariableCacheController::addDateTime(std::shared_ptr<Variable> variable,
                                          const SqpDateTime &dateTime)
{
    if (variable) {
        // TODO: squeeze the map to let it only some SqpDateTime without intersection
        impl->m_VariableToSqpDateTimeListMap[variable].push_back(dateTime);
    }
}
