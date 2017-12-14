#include "FuzzingDefs.h"

const QString NB_MAX_OPERATIONS_PROPERTY = QStringLiteral("component");
const QString NB_MAX_SYNC_GROUPS_PROPERTY = QStringLiteral("nbSyncGroups");
const QString NB_MAX_VARIABLES_PROPERTY = QStringLiteral("nbMaxVariables");
const QString AVAILABLE_OPERATIONS_PROPERTY = QStringLiteral("availableOperations");
const QString CACHE_TOLERANCE_PROPERTY = QStringLiteral("cacheTolerance");
const QString INITIAL_RANGE_PROPERTY = QStringLiteral("initialRange");
const QString MAX_RANGE_PROPERTY = QStringLiteral("maxRange");
const QString METADATA_POOL_PROPERTY = QStringLiteral("metadataPool");
const QString PROVIDER_PROPERTY = QStringLiteral("provider");
const QString OPERATION_DELAY_PROPERTY = QStringLiteral("operationDelay");
const QString VALIDATORS_PROPERTY = QStringLiteral("validators");

// //////////// //
// FuzzingState //
// //////////// //

const SyncGroup &FuzzingState::syncGroup(SyncGroupId id) const
{
    return m_SyncGroupsPool.at(id);
}

SyncGroup &FuzzingState::syncGroup(SyncGroupId id)
{
    return m_SyncGroupsPool.at(id);
}

const VariableState &FuzzingState::variableState(VariableId id) const
{
    return m_VariablesPool.at(id);
}

VariableState &FuzzingState::variableState(VariableId id)
{
    return m_VariablesPool.at(id);
}

SyncGroupId FuzzingState::syncGroupId(VariableId variableId) const
{
    auto end = m_SyncGroupsPool.cend();
    auto it
        = std::find_if(m_SyncGroupsPool.cbegin(), end, [&variableId](const auto &syncGroupEntry) {
              const auto &syncGroup = syncGroupEntry.second;
              return syncGroup.m_Variables.find(variableId) != syncGroup.m_Variables.end();
          });

    return it != end ? it->first : SyncGroupId{};
}

