#ifndef SCIQLOP_FUZZINGDEFS_H
#define SCIQLOP_FUZZINGDEFS_H

#include <Data/SqpRange.h>

#include <QString>
#include <QUuid>
#include <QVariantHash>

#include <memory>
#include <set>

// /////// //
// Aliases //
// /////// //

using MetadataPool = std::vector<QVariantHash>;
Q_DECLARE_METATYPE(MetadataPool)

using Properties = QVariantHash;

// ///////// //
// Constants //
// ///////// //

/// Max number of operations to generate
extern const QString NB_MAX_OPERATIONS_PROPERTY;

/// Max number of sync groups to create through operations
extern const QString NB_MAX_SYNC_GROUPS_PROPERTY;

/// Max number of variables to manipulate through operations
extern const QString NB_MAX_VARIABLES_PROPERTY;

/// Set of operations available for the test
extern const QString AVAILABLE_OPERATIONS_PROPERTY;

/// Tolerance used for variable's cache (in ratio)
extern const QString CACHE_TOLERANCE_PROPERTY;

/// Range with which the timecontroller is initialized
extern const QString INITIAL_RANGE_PROPERTY;

/// Max range that an operation can reach
extern const QString MAX_RANGE_PROPERTY;

/// Set of metadata that can be associated to a variable
extern const QString METADATA_POOL_PROPERTY;

/// Provider used to retrieve data
extern const QString PROVIDER_PROPERTY;

/// Min/max times left for an operation to execute
extern const QString OPERATION_DELAY_BOUNDS_PROPERTY;

/// Validators used to validate an operation
extern const QString VALIDATORS_PROPERTY;

// /////// //
// Structs //
// /////// //

class Variable;
struct VariableState {
    std::shared_ptr<Variable> m_Variable{nullptr};
    SqpRange m_Range{INVALID_RANGE};
};

using VariableId = int;
using VariablesPool = std::map<VariableId, VariableState>;

/**
 * Defines a synchronization group for a fuzzing state. A group reports the variables synchronized
 * with each other, and the current range of the group (i.e. range of the last synchronized variable
 * that has been moved)
 */
struct SyncGroup {
    std::set<VariableId> m_Variables{};
    SqpRange m_Range{INVALID_RANGE};
};

using SyncGroupId = QUuid;
using SyncGroupsPool = std::map<SyncGroupId, SyncGroup>;

/**
 * Defines a current state during a fuzzing state. It contains all the variables manipulated during
 * the test, as well as the synchronization status of these variables.
 */
struct FuzzingState {
    const SyncGroup &syncGroup(SyncGroupId id) const;
    SyncGroup &syncGroup(SyncGroupId id);

    const VariableState &variableState(VariableId id) const;
    VariableState &variableState(VariableId id);

    /// @return the identifier of the synchronization group in which the variable passed in
    /// parameter is located. If the variable is not in any group, returns an invalid identifier
    SyncGroupId syncGroupId(VariableId variableId) const;

    /// @return the set of synchronization group identifiers
    std::vector<SyncGroupId> syncGroupsIds() const;

    /// Updates fuzzing state according to a variable synchronization
    /// @param variableId the variable that is synchronized
    /// @param syncGroupId the synchronization group
    void synchronizeVariable(VariableId variableId, SyncGroupId syncGroupId);

    /// Updates fuzzing state according to a variable desynchronization
    /// @param variableId the variable that is desynchronized
    /// @param syncGroupId the synchronization group from which to remove the variable
    void desynchronizeVariable(VariableId variableId, SyncGroupId syncGroupId);

    /// Updates the range of a variable and all variables to which it is synchronized
    /// @param the variable for which to affect the range
    /// @param the range to affect
    void updateRanges(VariableId variableId, const SqpRange &newRange);

    VariablesPool m_VariablesPool;
    SyncGroupsPool m_SyncGroupsPool;
};

#endif // SCIQLOP_FUZZINGDEFS_H
