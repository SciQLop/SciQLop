#ifndef SCIQLOP_FUZZINGDEFS_H
#define SCIQLOP_FUZZINGDEFS_H

#include <QString>
#include <QVariantHash>

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

/// Max range that an operation can reach
extern const QString MAX_RANGE_PROPERTY;

/// Set of metadata that can be associated to a variable
extern const QString METADATA_POOL_PROPERTY;

/// Provider used to retrieve data
extern const QString PROVIDER_PROPERTY;

/// Time left for an operation to execute
extern const QString OPERATION_DELAY_PROPERTY;

#endif // SCIQLOP_FUZZINGDEFS_H
