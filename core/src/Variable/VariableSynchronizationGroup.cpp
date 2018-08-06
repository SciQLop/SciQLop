#include "Variable/VariableSynchronizationGroup.h"

#include "Variable/Variable.h"


Q_LOGGING_CATEGORY(LOG_VariableSynchronizationGroup, "VariableSynchronizationGroup")

struct VariableSynchronizationGroup::VariableSynchronizationGroupPrivate {

    std::set<QUuid> m_VariableIdSet;
};


VariableSynchronizationGroup::VariableSynchronizationGroup(QObject *parent)
        : QObject{parent}, impl{spimpl::make_unique_impl<VariableSynchronizationGroupPrivate>()}
{
}

VariableSynchronizationGroup::VariableSynchronizationGroup(QUuid variable, QObject *parent)
    :QObject{parent}, impl{spimpl::make_unique_impl<VariableSynchronizationGroupPrivate>()}
{
    this->addVariable(variable);
}

void VariableSynchronizationGroup::addVariable(QUuid vIdentifier)
{
    impl->m_VariableIdSet.insert(vIdentifier);
}

void VariableSynchronizationGroup::removeVariable(QUuid vIdentifier)
{
    impl->m_VariableIdSet.erase(vIdentifier);
}

const std::set<QUuid> &VariableSynchronizationGroup::getIds() const noexcept
{
    return impl->m_VariableIdSet;
}
