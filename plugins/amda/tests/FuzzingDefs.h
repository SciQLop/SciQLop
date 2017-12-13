#ifndef SCIQLOP_FUZZINGDEFS_H
#define SCIQLOP_FUZZINGDEFS_H

#include <Data/SqpRange.h>

#include <QString>
#include <QVariantHash>

#include <memory>

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

/// Time left for an operation to execute
extern const QString OPERATION_DELAY_PROPERTY;

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

#endif // SCIQLOP_FUZZINGDEFS_H
