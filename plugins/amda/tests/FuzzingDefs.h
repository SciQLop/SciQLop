#ifndef SCIQLOP_FUZZINGDEFS_H
#define SCIQLOP_FUZZINGDEFS_H

#include <QString>
// /////// //
// Aliases //
// /////// //

using Properties = QVariantHash;

// ///////// //
// Constants //
// ///////// //

/// Max number of operations to generate
extern const QString NB_MAX_OPERATIONS_PROPERTY;

/// Max number of variables to manipulate through operations
extern const QString NB_MAX_VARIABLES_PROPERTY;

#endif // SCIQLOP_FUZZINGDEFS_H
