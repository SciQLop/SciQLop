#include "FuzzingDefs.h"

const QString ACQUISITION_TIMEOUT_PROPERTY = QStringLiteral("acquisitionTimeout");
const QString NB_MAX_OPERATIONS_PROPERTY = QStringLiteral("component");
const QString NB_MAX_SYNC_GROUPS_PROPERTY = QStringLiteral("nbSyncGroups");
const QString NB_MAX_VARIABLES_PROPERTY = QStringLiteral("nbMaxVariables");
const QString AVAILABLE_OPERATIONS_PROPERTY = QStringLiteral("availableOperations");
const QString CACHE_TOLERANCE_PROPERTY = QStringLiteral("cacheTolerance");
const QString INITIAL_RANGE_PROPERTY = QStringLiteral("initialRange");
const QString MAX_RANGE_PROPERTY = QStringLiteral("maxRange");
const QString METADATA_POOL_PROPERTY = QStringLiteral("metadataPool");
const QString PROVIDER_PROPERTY = QStringLiteral("provider");
const QString OPERATION_DELAY_BOUNDS_PROPERTY = QStringLiteral("operationDelays");
const QString VALIDATORS_PROPERTY = QStringLiteral("validators");
const QString VALIDATION_FREQUENCY_BOUNDS_PROPERTY = QStringLiteral("validationFrequencyBounds");

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

std::vector<SyncGroupId> FuzzingState::syncGroupsIds() const
{
    std::vector<SyncGroupId> result{};

    for (const auto &entry : m_SyncGroupsPool) {
        result.push_back(entry.first);
    }

    return result;
}

void FuzzingState::synchronizeVariable(VariableId variableId, SyncGroupId syncGroupId)
{
    if (syncGroupId.isNull()) {
        return;
    }

    // Registers variable into sync group
    auto &syncGroup = m_SyncGroupsPool.at(syncGroupId);
    auto &variableState = m_VariablesPool.at(variableId);
    syncGroup.m_Variables.insert(variableId);
    if (syncGroup.m_Variables.size() == 1) {
        // If it's the first variable, sets the variable range as the sync group range
        syncGroup.m_Range = variableState.m_Range;
    }
    else {
        // If a variable is added to an existing group, sets its range to the group's range
        variableState.m_Range = syncGroup.m_Range;
    }
}

void FuzzingState::desynchronizeVariable(VariableId variableId, SyncGroupId syncGroupId)
{
    if (syncGroupId.isNull()) {
        return;
    }

    // Unregisters variable from sync group: if there is no more variable in the group, resets the
    // range
    auto &syncGroup = m_SyncGroupsPool.at(syncGroupId);
    syncGroup.m_Variables.erase(variableId);
    if (syncGroup.m_Variables.empty()) {
        syncGroup.m_Range = INVALID_RANGE;
    }
}

void FuzzingState::updateRanges(VariableId variableId, const DateTimeRange &newRange)
{
    auto syncGroupId = this->syncGroupId(variableId);

    // Retrieves the variables to update:
    // - if the variable is synchronized to others, updates the range of the group and of all
    // synchronized variables
    // - otherwise, updates only the variable
    if (syncGroupId.isNull()) {
        m_VariablesPool.at(variableId).m_Range = newRange;
    }
    else {
        auto &syncGroup = m_SyncGroupsPool.at(syncGroupId);
        syncGroup.m_Range = newRange;

        for (const auto &variableId : syncGroup.m_Variables) {
            m_VariablesPool.at(variableId).m_Range = newRange;
        }
    }
}
